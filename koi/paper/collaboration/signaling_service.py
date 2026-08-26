"""Content-blind WebSocket rendezvous service for WebRTC collaboration.

Deploy this ASGI app as one small, single-replica Serverless Container:

    uvicorn koi.paper.collaboration.signaling_service:app --host 0.0.0.0 --port 8080

It routes SDP/ICE metadata only. Document updates never pass through this app.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from koi.adapters.settings_store import load_env_file
from koi.paper.collaboration.network import verify_room_token
from koi.paper.collaboration.yandex_ws import GatewaySocket

load_env_file()

MAX_ROOM_PEERS = 5
PEER_TTL_S = 600
ROUTED_TYPES = {"offer", "answer", "ice_candidate", "relay"}
METADATA_KEYS = (
    "user_name",
    "actor_type",
    "git_commit",
    "base_document_hash",
    "document_hash",
    "crdt_epoch",
    "lan_ip",
)

app = FastAPI(
    title="ResearchOS Collaboration Signaling",
    description="Ephemeral WebRTC discovery; does not receive paper content.",
    version="0.1.0",
)


@dataclass
class SignalPeer:
    peer_id: str
    websocket: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    connection_id: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "joined_at": self.joined_at,
            **self.metadata,
        }


class SignalRooms:
    def __init__(self) -> None:
        self.rooms: dict[str, dict[str, SignalPeer]] = {}
        self.connections: dict[str, tuple[str, str]] = {}
        self.lock = asyncio.Lock()

    async def join(self, room: str, peer: SignalPeer) -> tuple[list[dict[str, Any]], str]:
        async with self.lock:
            peers = self.rooms.setdefault(room, {})
            self._remove_expired_locked(room, peers)
            if peer.peer_id not in peers and len(peers) >= MAX_ROOM_PEERS:
                raise ValueError("room is full")
            replaced = peers.get(peer.peer_id)
            if replaced and replaced.connection_id and replaced.connection_id != peer.connection_id:
                self.connections.pop(replaced.connection_id, None)
            previous = [item for item in peers.values() if item.peer_id != peer.peer_id]
            peers[peer.peer_id] = peer
            if peer.connection_id:
                self.connections[peer.connection_id] = (room, peer.peer_id)
            authority = min(peers.values(), key=lambda item: item.joined_at).peer_id
            return [item.public() for item in previous], authority

    async def get(self, room: str, peer_id: str) -> SignalPeer | None:
        async with self.lock:
            peers = self.rooms.get(room, {})
            self._remove_expired_locked(room, peers)
            return peers.get(peer_id)

    async def touch(self, room: str, peer_id: str) -> None:
        async with self.lock:
            peer = self.rooms.get(room, {}).get(peer_id)
            if peer:
                peer.last_seen = time.time()

    async def peers(self, room: str, *, exclude: str | None = None) -> list[SignalPeer]:
        async with self.lock:
            peers = self.rooms.get(room, {})
            self._remove_expired_locked(room, peers)
            return [peer for peer in peers.values() if peer.peer_id != exclude]

    async def leave(
        self,
        room: str,
        peer_id: str,
        websocket: Any | None = None,
        connection_id: str | None = None,
    ) -> list[SignalPeer]:
        async with self.lock:
            peers = self.rooms.get(room, {})
            current = peers.get(peer_id)
            if current is not None:
                if connection_id and current.connection_id and current.connection_id != connection_id:
                    return []
                if (
                    not connection_id
                    and websocket is not None
                    and current.websocket is not websocket
                ):
                    return []
            peers.pop(peer_id, None)
            if current and current.connection_id:
                self.connections.pop(current.connection_id, None)
            remaining = list(peers.values())
            if not peers:
                self.rooms.pop(room, None)
            return remaining

    def lookup_connection(self, connection_id: str) -> tuple[str, str] | None:
        return self.connections.get(connection_id)

    def _remove_expired_locked(self, room: str, peers: dict[str, SignalPeer]) -> None:
        cutoff = time.time() - PEER_TTL_S
        for peer_id in [
            key
            for key, peer in peers.items()
            if peer.last_seen < cutoff and not (peer.connection_id and peer.connection_id in self.connections)
        ]:
            gone = peers.pop(peer_id, None)
            if gone and gone.connection_id:
                self.connections.pop(gone.connection_id, None)


rooms = SignalRooms()


async def _send_many(peers: list[SignalPeer], payload: dict[str, Any]) -> None:
    for peer in peers:
        try:
            await peer.websocket.send_json(payload)
        except Exception:
            continue


def _safe_metadata(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {key: raw.get(key) for key in METADATA_KEYS if raw.get(key) is not None}


def _verify_join(first: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    secret = os.environ.get("KOI_COLLAB_TOKEN_SECRET", "").strip()
    claims = verify_room_token(str(first.get("token") or ""), secret=secret)
    room = str(claims["room"])
    peer_id = str(claims["peer"])
    if "read" not in (claims.get("permissions") or []):
        raise ValueError("token does not grant room access")
    if first.get("room_id") != room or first.get("peer_id") != peer_id:
        raise ValueError("join identity does not match token")
    return room, peer_id, _safe_metadata(first.get("metadata"))


async def accept_join(sender: Any, first: dict[str, Any], *, connection_id: str = "") -> tuple[str, str]:
    room, peer_id, metadata = _verify_join(first)
    peer = SignalPeer(
        peer_id=peer_id,
        websocket=sender,
        metadata=metadata,
        connection_id=connection_id,
    )
    existing, authority = await rooms.join(room, peer)
    await sender.send_json(
        {
            "type": "room_state",
            "room_id": room,
            "peers": existing,
            "authority_peer_id": authority,
        }
    )
    await _send_many(
        await rooms.peers(room, exclude=peer_id),
        {
            "type": "peer_joined",
            "room_id": room,
            "peer": peer.public(),
            "authority_peer_id": authority,
        },
    )
    return room, peer_id


async def handle_routed(sender: Any, room: str, peer_id: str, message: dict[str, Any]) -> None:
    kind = str(message.get("type") or "")
    await rooms.touch(room, peer_id)
    if kind == "heartbeat":
        await sender.send_json({"type": "heartbeat_ack", "at": time.time()})
        return
    if kind == "leave":
        remaining = await rooms.leave(room, peer_id, sender, connection_id=getattr(sender, "connection_id", "") or None)
        await _send_many(remaining, {"type": "peer_left", "room_id": room, "peer_id": peer_id})
        return
    if kind not in ROUTED_TYPES:
        await sender.send_json({"type": "error", "code": "unsupported_message"})
        return
    target_id = str(message.get("to") or "")
    target = await rooms.get(room, target_id)
    routed = {
        "type": kind,
        "room_id": room,
        "from": peer_id,
        "to": target_id,
        "payload": message.get("payload") or {},
    }
    if target is not None:
        await target.websocket.send_json(routed)
        return
    # Stale `to` after a reconnect: still deliver paper relay to whoever is left.
    if kind == "relay":
        others = await rooms.peers(room, exclude=peer_id)
        if others:
            await _send_many(others, routed)
            return
    await sender.send_json({"type": "error", "code": "peer_not_found", "peer_id": target_id})


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.websocket("/signal")
async def signal(websocket: WebSocket) -> None:
    await websocket.accept()
    room = ""
    peer_id = ""
    try:
        first = await websocket.receive_json()
        if first.get("type") != "join":
            await websocket.close(code=1008, reason="first message must be join")
            return
        try:
            room, peer_id = await accept_join(websocket, first)
        except ValueError as exc:
            await websocket.close(code=1008, reason=str(exc))
            return
        while True:
            message = await websocket.receive_json()
            if str(message.get("type") or "") == "leave":
                break
            await handle_routed(websocket, room, peer_id, message)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if room and peer_id:
            remaining = await rooms.leave(room, peer_id, websocket)
            await _send_many(
                remaining,
                {"type": "peer_left", "room_id": room, "peer_id": peer_id},
            )


@app.api_route("/signal", methods=["GET", "POST"])
@app.api_route("/yc/ws", methods=["GET", "POST"])
async def yandex_websocket_event(request: Request) -> Response:
    """API Gateway WebSocket → HTTP. Rooms stay in this process (one replica).

    The gateway keeps the client path (`/signal`) when invoking a container;
    `path: /yc/ws` in the OpenAPI spec is ignored. Both URLs accept the same
    CONNECT / MESSAGE / DISCONNECT events.
    """
    event = (request.headers.get("X-Yc-Apigateway-Websocket-Event-Type") or "").upper()
    connection_id = request.headers.get("X-Yc-Apigateway-Websocket-Connection-Id") or ""
    if not event:
        event = "CONNECT" if request.method == "GET" else "MESSAGE"
    if event == "CONNECT":
        return JSONResponse({"ok": True})
    if event == "DISCONNECT":
        found = rooms.lookup_connection(connection_id)
        if found:
            room, peer_id = found
            remaining = await rooms.leave(room, peer_id, connection_id=connection_id)
            await _send_many(remaining, {"type": "peer_left", "room_id": room, "peer_id": peer_id})
        return JSONResponse({"ok": True})
    raw = await request.body()
    try:
        message = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"type": "error", "code": "invalid_json"}, status_code=400)
    if not isinstance(message, dict):
        return JSONResponse({"type": "error", "code": "invalid_json"}, status_code=400)
    sender = GatewaySocket(connection_id)
    if message.get("type") == "join":
        try:
            await accept_join(sender, message, connection_id=connection_id)
        except ValueError as exc:
            return JSONResponse({"type": "error", "code": str(exc)}, status_code=403)
        return Response(status_code=204)
    found = rooms.lookup_connection(connection_id)
    if found is None:
        return JSONResponse({"type": "error", "code": "not_joined"})
    room, peer_id = found
    await handle_routed(sender, room, peer_id, message)
    return Response(status_code=204)

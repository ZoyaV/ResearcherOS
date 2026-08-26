"""Content-blind WebSocket rendezvous service for WebRTC collaboration.

Deploy this ASGI app as one small, single-replica Serverless Container:

    uvicorn koi.paper.collaboration.signaling_service:app --host 0.0.0.0 --port 8080

It routes SDP/ICE metadata only. Document updates never pass through this app.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from koi.adapters.settings_store import load_env_file
from koi.paper.collaboration.network import verify_room_token

load_env_file()

MAX_ROOM_PEERS = 5
PEER_TTL_S = 45
ROUTED_TYPES = {"offer", "answer", "ice_candidate", "relay"}

app = FastAPI(
    title="ResearchOS Collaboration Signaling",
    description="Ephemeral WebRTC discovery; does not receive paper content.",
    version="0.1.0",
)


@dataclass
class SignalPeer:
    peer_id: str
    websocket: WebSocket
    metadata: dict[str, Any] = field(default_factory=dict)
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "joined_at": self.joined_at,
            **self.metadata,
        }


class SignalRooms:
    def __init__(self) -> None:
        self.rooms: dict[str, dict[str, SignalPeer]] = {}
        self.lock = asyncio.Lock()

    async def join(self, room: str, peer: SignalPeer) -> tuple[list[dict[str, Any]], str]:
        async with self.lock:
            peers = self.rooms.setdefault(room, {})
            self._remove_expired_locked(room, peers)
            if peer.peer_id not in peers and len(peers) >= MAX_ROOM_PEERS:
                raise ValueError("room is full")
            previous = list(peers.values())
            peers[peer.peer_id] = peer
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
        websocket: WebSocket | None = None,
    ) -> list[SignalPeer]:
        async with self.lock:
            peers = self.rooms.get(room, {})
            current = peers.get(peer_id)
            if websocket is not None and current is not None and current.websocket is not websocket:
                return []
            peers.pop(peer_id, None)
            remaining = list(peers.values())
            if not peers:
                self.rooms.pop(room, None)
            return remaining

    def _remove_expired_locked(self, room: str, peers: dict[str, SignalPeer]) -> None:
        cutoff = time.time() - PEER_TTL_S
        for peer_id in [key for key, peer in peers.items() if peer.last_seen < cutoff]:
            peers.pop(peer_id, None)


rooms = SignalRooms()


async def _send_many(peers: list[SignalPeer], payload: dict[str, Any]) -> None:
    for peer in peers:
        try:
            await peer.websocket.send_json(payload)
        except Exception:
            continue


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
        secret = os.environ.get("KOI_COLLAB_TOKEN_SECRET", "").strip()
        try:
            claims = verify_room_token(str(first.get("token") or ""), secret=secret)
        except ValueError as exc:
            await websocket.close(code=1008, reason=str(exc))
            return
        room = str(claims["room"])
        peer_id = str(claims["peer"])
        if "read" not in (claims.get("permissions") or []):
            await websocket.close(code=1008, reason="token does not grant room access")
            return
        if first.get("room_id") != room or first.get("peer_id") != peer_id:
            await websocket.close(code=1008, reason="join identity does not match token")
            return
        metadata = first.get("metadata")
        safe_metadata = {
            key: metadata.get(key)
            for key in (
                "user_name",
                "actor_type",
                "git_commit",
                "base_document_hash",
                "document_hash",
                "crdt_epoch",
                "lan_ip",
            )
            if isinstance(metadata, dict) and metadata.get(key) is not None
        }
        peer = SignalPeer(peer_id=peer_id, websocket=websocket, metadata=safe_metadata)
        try:
            existing, authority = await rooms.join(room, peer)
        except ValueError as exc:
            await websocket.close(code=1008, reason=str(exc))
            return
        await websocket.send_json(
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

        while True:
            message = await websocket.receive_json()
            kind = str(message.get("type") or "")
            await rooms.touch(room, peer_id)
            if kind == "heartbeat":
                await websocket.send_json({"type": "heartbeat_ack", "at": time.time()})
                continue
            if kind == "leave":
                break
            if kind not in ROUTED_TYPES:
                await websocket.send_json({"type": "error", "code": "unsupported_message"})
                continue
            target_id = str(message.get("to") or "")
            target = await rooms.get(room, target_id)
            if target is None:
                await websocket.send_json(
                    {"type": "error", "code": "peer_not_found", "peer_id": target_id}
                )
                continue
            await target.websocket.send_json(
                {
                    "type": kind,
                    "room_id": room,
                    "from": peer_id,
                    "to": target_id,
                    "payload": message.get("payload") or {},
                }
            )
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if room and peer_id:
            remaining = await rooms.leave(room, peer_id, websocket)
            await _send_many(
                remaining,
                {"type": "peer_left", "room_id": room, "peer_id": peer_id},
            )

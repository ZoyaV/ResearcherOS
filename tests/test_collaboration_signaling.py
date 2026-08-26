"""Spike B: room credentials, signaling routing, and safe CRDT bootstrap."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from koi.paper.collaboration.network import git_document_state, issue_room_token, lan_ip, verify_room_token
from koi.paper.collaboration.session import CollabSession
from koi.paper.collaboration.signaling_service import (
    ROUTED_TYPES,
    SignalPeer,
    SignalRooms,
    _send_many,
    handle_routed,
    rooms,
)


@pytest.fixture(autouse=True)
def _clear_signal_rooms():
    rooms.rooms.clear()
    rooms.connections.clear()
    yield
    rooms.rooms.clear()
    rooms.connections.clear()


def test_signaling_routes_relay_fallback() -> None:
    assert "relay" in ROUTED_TYPES


def test_lan_ip_prefers_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOI_COLLAB_LAN_IP", "192.168.0.110")
    assert lan_ip() == "192.168.0.110"


def test_room_token_rejects_tampering_and_expiration() -> None:
    token, _ = issue_room_token(
        secret="secret",
        room="room-a",
        peer_id="alice",
        repository_id="github.com/example/paper",
        paper_id="emnlp",
        now=100,
        ttl_s=300,
    )
    claims = verify_room_token(token, secret="secret", now=200)
    assert claims["room"] == "room-a"
    assert claims["peer"] == "alice"
    with pytest.raises(ValueError, match="signature"):
        verify_room_token(f"{token[:-1]}x", secret="secret", now=200)
    with pytest.raises(ValueError, match="expired"):
        verify_room_token(token, secret="secret", now=401)


def test_signaling_room_tracks_authority_and_routes_opaque_payload() -> None:
    class Socket:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        async def send_json(self, payload: dict) -> None:
            self.messages.append(payload)

    async def scenario() -> None:
        room_store = SignalRooms()
        alice_socket = Socket()
        bob_socket = Socket()
        metadata = {
            "git_commit": "abc123",
            "base_document_hash": "base",
            "document_hash": "current",
            "crdt_epoch": "epoch-a",
        }
        alice = SignalPeer("alice", alice_socket, metadata=metadata)
        bob = SignalPeer("bob", bob_socket, metadata={**metadata, "crdt_epoch": "epoch-b"})
        existing, authority = await room_store.join("paper-room", alice)
        assert existing == []
        assert authority == "alice"
        existing, authority = await room_store.join("paper-room", bob)
        assert existing[0]["peer_id"] == "alice"
        assert authority == "alice"

        payload = {
            "type": "offer",
            "room_id": "paper-room",
            "from": "bob",
            "to": "alice",
            "payload": {"sdp": {"type": "offer", "sdp": "opaque"}},
        }
        await _send_many([alice], payload)
        assert alice_socket.messages == [payload]
        assert "document" not in alice_socket.messages[0]

    asyncio.run(scenario())


def test_relay_reaches_room_when_target_id_is_stale() -> None:
    class Socket:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        async def send_json(self, payload: dict) -> None:
            self.messages.append(payload)

    async def scenario() -> None:
        alice_socket = Socket()
        bob_socket = Socket()
        await rooms.join("paper-room", SignalPeer("alice", alice_socket, connection_id="c-a"))
        await rooms.join("paper-room", SignalPeer("bob", bob_socket, connection_id="c-b"))
        await handle_routed(
            alice_socket,
            "paper-room",
            "alice",
            {"type": "relay", "to": "gone-peer", "payload": {"type": "update"}},
        )
        assert bob_socket.messages[0]["type"] == "relay"
        assert bob_socket.messages[0]["payload"] == {"type": "update"}
        assert alice_socket.messages == []

        existing, _ = await rooms.join(
            "paper-room",
            SignalPeer("alice", alice_socket, connection_id="c-a2"),
        )
        assert [item["peer_id"] for item in existing] == ["bob"]

    asyncio.run(scenario())


def test_relay_drops_closed_gateway_target_and_falls_back() -> None:
    class Socket:
        def __init__(self, *, closed: bool = False) -> None:
            self.closed = closed
            self.messages: list[dict] = []

        async def send_json(self, payload: dict) -> None:
            if self.closed:
                raise RuntimeError("gateway connection is gone")
            self.messages.append(payload)

    async def scenario() -> None:
        alice_socket = Socket()
        stale_socket = Socket(closed=True)
        bob_socket = Socket()
        room = "paper-room-closed-target"
        await rooms.join(room, SignalPeer("alice", alice_socket, connection_id="closed-a"))
        await rooms.join(room, SignalPeer("stale", stale_socket, connection_id="closed-stale"))
        await rooms.join(room, SignalPeer("bob", bob_socket, connection_id="closed-b"))

        await handle_routed(
            alice_socket,
            room,
            "alice",
            {"type": "relay", "to": "stale", "payload": {"type": "update"}},
        )

        assert rooms.lookup_connection("closed-stale") is None
        assert bob_socket.messages[-1]["type"] == "relay"
        assert bob_socket.messages[-1]["payload"] == {"type": "update"}

    asyncio.run(scenario())


def test_adopting_authority_state_does_not_duplicate_seed_text(tmp_path: Path) -> None:
    left_path = tmp_path / "left" / "main.tex"
    right_path = tmp_path / "right" / "main.tex"
    left_path.parent.mkdir()
    right_path.parent.mkdir()
    left_path.write_text("same seed\n", encoding="utf-8")
    right_path.write_text("same seed\n", encoding="utf-8")
    left = CollabSession(
        "left",
        "paper",
        left_path,
        watch=False,
        proposal_root=tmp_path / "left-proposals",
    )
    right = CollabSession(
        "right",
        "paper",
        right_path,
        watch=False,
        proposal_root=tmp_path / "right-proposals",
    )
    try:
        left.document.apply_edit(len("same seed"), 0, " from Alice")
        event = right.adopt_remote_state(
            left.document.get_update(),
            crdt_epoch=left.crdt_epoch,
            expected_hash=left.document.content_hash(),
            origin="bob",
        )
        assert right.document.to_string() == "same seed from Alice\n"
        assert right.document.to_string().count("same seed") == 1
        assert right.crdt_epoch == left.crdt_epoch
        assert event["type"] == "reset_sync"
        assert right_path.read_text(encoding="utf-8") == right.document.to_string()
    finally:
        left.close()
        right.close()


def test_adopting_remote_state_checks_claimed_hash(tmp_path: Path) -> None:
    tex = tmp_path / "main.tex"
    tex.write_text("local\n", encoding="utf-8")
    remote = CollabSession(
        "remote", "paper", tmp_path / "remote.tex", watch=False, proposal_root=tmp_path / "p1"
    )
    local = CollabSession(
        "local", "paper", tex, watch=False, proposal_root=tmp_path / "p2"
    )
    try:
        with pytest.raises(ValueError, match="hash"):
            local.adopt_remote_state(
                remote.document.get_update(),
                crdt_epoch=remote.crdt_epoch,
                expected_hash="not-the-update-hash",
            )
        assert local.document.to_string() == "local\n"
    finally:
        remote.close()
        local.close()


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.test", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_git_document_state_uses_tex_checkout_not_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README").write_text("code clone\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-qm", "Initial commit")
    _git(repo, "branch", "-M", "main")
    code_commit = _git(repo, "rev-parse", "HEAD")

    worktree = tmp_path / "tree" / "paper"
    _git(repo, "worktree", "add", "-B", "ResearcherOS", str(worktree))
    tex = worktree / "koi-structure" / "paper" / "neurips" / "main.tex"
    tex.parent.mkdir(parents=True)
    tex.write_text("paper body\n", encoding="utf-8")
    _git(worktree, "add", "koi-structure/paper/neurips/main.tex")
    _git(worktree, "commit", "-qm", "Add paper")
    paper_commit = _git(worktree, "rev-parse", "HEAD")
    assert paper_commit != code_commit

    monkeypatch.setattr(
        "koi.paper.collaboration.network.repo_root",
        lambda _project_id: repo,
    )
    state = git_document_state("demo", tex)
    assert state.commit == paper_commit
    assert state.relative_path == "koi-structure/paper/neurips/main.tex"
    assert state.base_document_hash


def test_yandex_gateway_join_and_route(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from koi.paper.collaboration.signaling_service import app

    sent: list[tuple[str, dict]] = []

    async def fake_send(connection_id: str, payload: dict) -> None:
        sent.append((connection_id, payload))

    monkeypatch.setenv("KOI_COLLAB_TOKEN_SECRET", "secret")
    monkeypatch.setattr("koi.paper.collaboration.yandex_ws.send_apigw_json", fake_send)
    token, _ = issue_room_token(
        secret="secret",
        room="room-a",
        peer_id="alice",
        repository_id="github.com/example/paper",
        paper_id="emnlp",
    )
    client = TestClient(app)
    connect = client.get(
        "/signal",
        headers={
            "X-Yc-Apigateway-Websocket-Event-Type": "CONNECT",
            "X-Yc-Apigateway-Websocket-Connection-Id": "conn-alice",
        },
    )
    assert connect.status_code == 200
    join = client.post(
        "/signal",
        headers={
            "X-Yc-Apigateway-Websocket-Event-Type": "MESSAGE",
            "X-Yc-Apigateway-Websocket-Connection-Id": "conn-alice",
        },
        json={
            "type": "join",
            "token": token,
            "room_id": "room-a",
            "peer_id": "alice",
            "metadata": {"git_commit": "abc"},
        },
    )
    assert join.status_code == 204
    assert rooms.lookup_connection("conn-alice") == ("room-a", "alice")
    assert any(item[1].get("type") == "room_state" for item in sent)

    disconnect = client.delete(
        "/signal",
        headers={
            "X-Yc-Apigateway-Websocket-Connection-Id": "conn-alice",
        },
    )
    assert disconnect.status_code == 200
    assert rooms.lookup_connection("conn-alice") is None

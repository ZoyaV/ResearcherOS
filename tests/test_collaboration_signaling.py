"""Spike B: room credentials, signaling routing, and safe CRDT bootstrap."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from koi.paper.collaboration.network import issue_room_token, verify_room_token
from koi.paper.collaboration.session import CollabSession
from koi.paper.collaboration.signaling_service import SignalPeer, SignalRooms, _send_many, rooms


@pytest.fixture(autouse=True)
def _clear_signal_rooms():
    rooms.rooms.clear()
    yield
    rooms.rooms.clear()


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

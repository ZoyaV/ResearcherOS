"""Configuration, identity, and short-lived credentials for P2P collaboration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from koi.adapters.paths import repo_root
from koi.paper.collaboration.ids import room_id
from koi.paper.collaboration.revisions import content_hash

TOKEN_TTL_S = 10 * 60
TOKEN_AUDIENCE = "researchos-collaboration"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _json_part(value: dict[str, Any]) -> str:
    return _b64url(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def issue_room_token(
    *,
    secret: str,
    room: str,
    peer_id: str,
    repository_id: str,
    paper_id: str,
    permissions: tuple[str, ...] = ("read", "write"),
    ttl_s: int = TOKEN_TTL_S,
    now: int | None = None,
) -> tuple[str, int]:
    """Create a compact HS256 token understood by the signaling service."""
    if not secret:
        raise ValueError("collaboration token secret is not configured")
    issued_at = int(time.time() if now is None else now)
    expires_at = issued_at + max(30, int(ttl_s))
    header = _json_part({"alg": "HS256", "typ": "JWT"})
    payload = _json_part(
        {
            "aud": TOKEN_AUDIENCE,
            "room": room,
            "repo": repository_id,
            "paper": paper_id,
            "peer": peer_id,
            "permissions": list(permissions),
            "iat": issued_at,
            "exp": expires_at,
        }
    )
    signing_input = f"{header}.{payload}"
    signature = _b64url(
        hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{signing_input}.{signature}", expires_at


def verify_room_token(
    token: str,
    *,
    secret: str,
    now: int | None = None,
) -> dict[str, Any]:
    """Verify a room token and return its claims."""
    if not secret:
        raise ValueError("collaboration token secret is not configured")
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = json.loads(_b64url_decode(header_part))
        claims = json.loads(_b64url_decode(payload_part))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid collaboration token") from exc
    if header.get("alg") != "HS256":
        raise ValueError("unsupported collaboration token algorithm")
    signing_input = f"{header_part}.{payload_part}"
    expected = hmac.new(
        secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    try:
        supplied = _b64url_decode(signature_part)
    except ValueError as exc:
        raise ValueError("invalid collaboration token signature") from exc
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("invalid collaboration token signature")
    current = int(time.time() if now is None else now)
    if claims.get("aud") != TOKEN_AUDIENCE:
        raise ValueError("invalid collaboration token audience")
    if int(claims.get("exp") or 0) <= current:
        raise ValueError("collaboration token expired")
    if not claims.get("room") or not claims.get("peer"):
        raise ValueError("collaboration token is missing room or peer")
    return claims


def _run_git(root: Path, *args: str, strip: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip() if strip else result.stdout


def _canonical_remote(value: str) -> str:
    remote = value.strip()
    if not remote:
        return ""
    if remote.startswith("git@") and ":" in remote:
        host_path = remote[4:].replace(":", "/", 1)
        remote = f"https://{host_path}"
    parsed = urlparse(remote)
    if parsed.hostname and parsed.path:
        return f"{parsed.hostname.lower()}/{parsed.path.strip('/').removesuffix('.git')}"
    return remote.removesuffix(".git")


@dataclass(frozen=True)
class GitDocumentState:
    repository_id: str
    commit: str
    base_document_hash: str
    relative_path: str


def git_document_state(project_id: str, tex_path: Path) -> GitDocumentState:
    """Describe the durable Git base without treating the working tree as authoritative."""
    root = repo_root(project_id)
    resolved = tex_path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = tex_path.name
    commit = _run_git(root, "rev-parse", "HEAD")
    remote = _canonical_remote(_run_git(root, "config", "--get", "remote.origin.url"))
    repository_id = remote or project_id
    base_text = _run_git(root, "show", f"HEAD:{relative}", strip=False) if commit else ""
    return GitDocumentState(
        repository_id=repository_id,
        commit=commit,
        base_document_hash=content_hash(base_text) if base_text else "",
        relative_path=relative,
    )


@dataclass(frozen=True)
class NetworkConfig:
    signaling_url: str
    token_secret: str
    stun_url: str
    turn_url: str
    turn_username: str
    turn_credential: str

    @property
    def enabled(self) -> bool:
        return bool(self.signaling_url and self.token_secret)

    def ice_servers(self) -> list[dict[str, Any]]:
        servers: list[dict[str, Any]] = []
        if self.stun_url:
            servers.append({"urls": [self.stun_url]})
        if self.turn_url and self.turn_username and self.turn_credential:
            servers.append(
                {
                    "urls": [self.turn_url],
                    "username": self.turn_username,
                    "credential": self.turn_credential,
                }
            )
        return servers


def network_config() -> NetworkConfig:
    return NetworkConfig(
        signaling_url=os.environ.get("KOI_COLLAB_SIGNALING_URL", "").strip(),
        token_secret=os.environ.get("KOI_COLLAB_TOKEN_SECRET", "").strip(),
        stun_url=os.environ.get("KOI_COLLAB_STUN_URL", "stun:stun.l.google.com:19302").strip(),
        turn_url=os.environ.get("KOI_COLLAB_TURN_URL", "").strip(),
        turn_username=os.environ.get("KOI_COLLAB_TURN_USERNAME", "").strip(),
        turn_credential=os.environ.get("KOI_COLLAB_TURN_CREDENTIAL", "").strip(),
    )


def network_room_id(repository_id: str, paper_id: str, relative_path: str) -> str:
    return room_id(repository_id, paper_id, relative_path)

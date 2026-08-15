"""Revision metadata for materialized collaborative documents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SIDECAR_NAME = ".collab.json"
MAX_SNAPSHOTS = 32


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RevisionRecord:
    revision: int
    content_hash: str
    timestamp: str
    document_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp,
            "document_id": self.document_id,
        }


@dataclass
class RevisionLog:
    """In-memory snapshots plus an optional sidecar next to ``main.tex``."""

    document_id: str = ""
    latest: RevisionRecord | None = None
    snapshots: dict[int, str] = field(default_factory=dict)

    def remember(self, revision: int, text: str) -> RevisionRecord:
        record = RevisionRecord(
            revision=revision,
            content_hash=content_hash(text),
            timestamp=utc_now(),
            document_id=self.document_id,
        )
        self.latest = record
        self.snapshots[revision] = text
        extra = sorted(self.snapshots)[:-MAX_SNAPSHOTS]
        for key in extra:
            self.snapshots.pop(key, None)
        return record

    def text_at(self, revision: int) -> str | None:
        return self.snapshots.get(revision)

    def write_sidecar(self, slot_dir: Path) -> None:
        if self.latest is None:
            return
        path = slot_dir / SIDECAR_NAME
        path.write_text(json.dumps(self.latest.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def read_sidecar(cls, slot_dir: Path) -> dict[str, Any]:
        path = slot_dir / SIDECAR_NAME
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

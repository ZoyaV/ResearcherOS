"""Persistent feed of research-question discoveries (git sync)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from koi.adapters.workspace import get_workspace

_ws = get_workspace()
FEED_PATH = _ws.run_dir / "rq-discoveries-feed.json"
MAX_ITEMS = 80


def _load() -> list[dict[str, Any]]:
    if not FEED_PATH.exists():
        return []
    try:
        data = json.loads(FEED_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and item.get("key")]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save(items: list[dict[str, Any]]) -> None:
    FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEED_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_discoveries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append new discoveries; return only items that were actually added."""
    if not items:
        return []
    now = datetime.now(timezone.utc).isoformat()
    feed = _load()
    known = {str(item.get("key")) for item in feed}
    added: list[dict[str, Any]] = []
    for raw in items:
        key = str(raw.get("key") or "").strip()
        if not key or key in known:
            continue
        entry = {
            "key": key,
            "project_id": str(raw.get("project_id") or "").strip(),
            "question_id": str(raw.get("question_id") or "").strip(),
            "question": str(raw.get("question") or "").strip(),
            "answer": str(raw.get("answer") or "").strip(),
            "author": str(raw.get("author") or "коллега").strip() or "коллега",
            "signature": str(raw.get("signature") or "").strip(),
            "discovered_at": now,
        }
        feed.append(entry)
        known.add(key)
        added.append(entry)
    if added:
        feed.sort(key=lambda x: x.get("discovered_at") or "", reverse=True)
        _save(feed[:MAX_ITEMS])
    return added


def list_feed(*, limit: int = 50) -> list[dict[str, Any]]:
    feed = _load()
    feed.sort(key=lambda x: x.get("discovered_at") or "", reverse=True)
    return feed[: max(1, min(limit, MAX_ITEMS))]

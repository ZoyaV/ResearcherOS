"""Queue of NeurIPS paper generation jobs from ResearchOS UI — for Cursor Paper Inbox."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, TypedDict
from uuid import uuid4

from koi.adapters.workspace import get_workspace

_ws = get_workspace()
QUEUE_PATH = _ws.run_dir / "paper-queue.json"
MAX_ITEMS = 20

PaperStatus = Literal["pending", "processing", "done", "error"]


class PaperItem(TypedDict, total=False):
    id: str
    project_id: str
    project_title: str
    enqueued_at: str
    status: PaperStatus
    processing_at: Optional[str]
    finished_at: Optional[str]
    error: Optional[str]


def _load() -> list[PaperItem]:
    if not QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [_normalize(item) for item in data if _valid_item(item)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save(items: list[PaperItem]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize(item: dict) -> PaperItem:
    return {
        "id": str(item["id"]),
        "project_id": str(item["project_id"]),
        "project_title": str(item.get("project_title") or ""),
        "enqueued_at": str(item["enqueued_at"]),
        "status": item.get("status") or "pending",
        "processing_at": item.get("processing_at") or None,
        "finished_at": item.get("finished_at") or None,
        "error": item.get("error") or None,
    }


def _valid_item(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    return all(
        isinstance(item.get(k), str) and item[k]
        for k in ("id", "project_id", "enqueued_at")
    )


def enqueue_paper(*, project_id: str, project_title: str) -> PaperItem:
    items = _load()
    items = [i for i in items if not (i["project_id"] == project_id and i.get("status") == "pending")]
    item: PaperItem = {
        "id": f"paper-{uuid4().hex[:10]}",
        "project_id": project_id,
        "project_title": project_title.strip(),
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "processing_at": None,
        "finished_at": None,
        "error": None,
    }
    items.append(item)
    if len(items) > MAX_ITEMS:
        items = items[-MAX_ITEMS:]
    _save(items)
    return item


def list_pending() -> list[PaperItem]:
    return [i for i in _load() if i.get("status", "pending") == "pending"]


def list_for_project(project_id: str, *, limit: int = 10) -> list[PaperItem]:
    items = [i for i in _load() if i["project_id"] == project_id]
    items.sort(key=lambda i: i["enqueued_at"], reverse=True)
    return items[:limit]


def find_item(item_id: str) -> Optional[PaperItem]:
    return next((i for i in _load() if i["id"] == item_id), None)


def mark_processing(item_id: str) -> PaperItem:
    items = _load()
    for item in items:
        if item["id"] != item_id:
            continue
        status = item.get("status") or "pending"
        if status in ("done", "error"):
            return item
        if status != "processing":
            item["status"] = "processing"
            item["processing_at"] = datetime.now(timezone.utc).isoformat()
            _save(items)
        return item
    raise KeyError(f"Paper queue item not found: {item_id}")


def mark_finished(item_id: str, *, error: str | None = None) -> PaperItem:
    items = _load()
    for item in items:
        if item["id"] != item_id:
            continue
        item["status"] = "error" if error else "done"
        item["finished_at"] = datetime.now(timezone.utc).isoformat()
        item["error"] = error
        _save(items)
        return item
    raise KeyError(f"Paper queue item not found: {item_id}")

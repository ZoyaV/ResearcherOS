"""Queue of Related Work drafts from ResearchOS UI — for Cursor agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, TypedDict
from uuid import uuid4

from koi.adapters.workspace import get_workspace

_ws = get_workspace()
QUEUE_PATH = _ws.run_dir / "related-work-queue.json"
MAX_ITEMS = 30

RelatedWorkStatus = Literal["pending", "processing", "answered"]


class RelatedWorkItem(TypedDict, total=False):
    id: str
    project_id: str
    problem: str
    question: str
    cluster_keys: list[str]
    cluster_labels: list[str]
    paper_count: int
    prompt: str
    enqueued_at: str
    status: RelatedWorkStatus
    markdown: Optional[str]
    processing_at: Optional[str]
    answered_at: Optional[str]


def _load() -> list[RelatedWorkItem]:
    if not QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [_normalize(item) for item in data if _valid_item(item)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save(items: list[RelatedWorkItem]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize(item: dict) -> RelatedWorkItem:
    cluster_keys = item.get("cluster_keys")
    cluster_labels = item.get("cluster_labels")
    out: RelatedWorkItem = {
        "id": str(item["id"]),
        "project_id": str(item["project_id"]),
        "problem": str(item["problem"]),
        "question": str(item.get("question") or ""),
        "cluster_keys": list(cluster_keys) if isinstance(cluster_keys, list) else [],
        "cluster_labels": list(cluster_labels) if isinstance(cluster_labels, list) else [],
        "paper_count": int(item.get("paper_count") or 0),
        "prompt": str(item.get("prompt") or ""),
        "enqueued_at": str(item["enqueued_at"]),
        "status": item.get("status") or "pending",
        "markdown": item.get("markdown") or None,
        "processing_at": item.get("processing_at") or None,
        "answered_at": item.get("answered_at") or None,
    }
    if out["status"] == "answered" and not out.get("markdown"):
        out["status"] = "pending"
        out["answered_at"] = None
    return out


def _valid_item(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    return all(
        isinstance(item.get(k), str) and item[k]
        for k in ("id", "project_id", "problem", "enqueued_at", "prompt")
    )


def enqueue_related_work(
    *,
    project_id: str,
    problem: str,
    question: str,
    cluster_keys: list[str],
    cluster_labels: list[str],
    paper_count: int,
    prompt: str,
) -> RelatedWorkItem:
    text = problem.strip()
    if not text:
        raise ValueError("Problem statement is empty")
    if not prompt.strip():
        raise ValueError("Related Work prompt is empty")
    items = _load()
    item: RelatedWorkItem = {
        "id": f"rw-{uuid4().hex[:10]}",
        "project_id": project_id,
        "problem": text,
        "question": question.strip(),
        "cluster_keys": list(cluster_keys),
        "cluster_labels": list(cluster_labels),
        "paper_count": paper_count,
        "prompt": prompt.strip(),
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "markdown": None,
        "processing_at": None,
        "answered_at": None,
    }
    items.append(item)
    if len(items) > MAX_ITEMS:
        items = items[-MAX_ITEMS:]
    _save(items)
    return item


def list_pending() -> list[RelatedWorkItem]:
    return [i for i in _load() if i.get("status", "pending") == "pending"]


def list_for_project(project_id: str, *, limit: int = 20) -> list[RelatedWorkItem]:
    items = [i for i in _load() if i["project_id"] == project_id]
    items.sort(key=lambda i: i["enqueued_at"], reverse=True)
    return items[:limit]


def find_item(item_id: str) -> Optional[RelatedWorkItem]:
    return next((i for i in _load() if i["id"] == item_id), None)


def mark_processing(item_id: str) -> RelatedWorkItem:
    items = _load()
    for item in items:
        if item["id"] != item_id:
            continue
        status = item.get("status") or "pending"
        if status == "answered":
            return item
        if status != "processing":
            item["status"] = "processing"
            item["processing_at"] = datetime.now(timezone.utc).isoformat()
            _save(items)
        return item
    raise KeyError(f"Related Work queue item not found: {item_id}")


def submit_markdown(item_id: str, markdown: str) -> RelatedWorkItem:
    text = markdown.strip()
    if not text:
        raise ValueError("Markdown is empty")
    items = _load()
    for item in items:
        if item["id"] != item_id:
            continue
        item["status"] = "answered"
        item["markdown"] = text
        item["answered_at"] = datetime.now(timezone.utc).isoformat()
        _save(items)
        return item
    raise KeyError(f"Related Work queue item not found: {item_id}")

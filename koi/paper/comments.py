"""Line-anchored review comments for project papers (sidecar comments.json)."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from koi.paper.generator import TEX_NAME

COMMENTS_NAME = "comments.json"
SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def comments_path(slot_dir: Path) -> Path:
    return slot_dir / COMMENTS_NAME


def _empty_store() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "file": TEX_NAME, "comments": []}


def load_comments(slot_dir: Path) -> dict[str, Any]:
    path = comments_path(slot_dir)
    if not path.is_file():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("file", TEX_NAME)
    data.setdefault("comments", [])
    if not isinstance(data["comments"], list):
        data["comments"] = []
    return data


def save_comments(slot_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    slot_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SCHEMA_VERSION,
        "file": TEX_NAME,
        "comments": data.get("comments") or [],
    }
    comments_path(slot_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def compute_content_hash(
    tex_text: str,
    line_start: int,
    line_end: int,
    char_start: int | None = None,
    char_end: int | None = None,
) -> str:
    chunk = extract_anchor_text(tex_text, line_start, line_end, char_start, char_end)
    if not chunk:
        return ""
    digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest}"


def extract_anchor_text(
    tex_text: str,
    line_start: int,
    line_end: int,
    char_start: int | None = None,
    char_end: int | None = None,
) -> str:
    lines = tex_text.splitlines()
    start = max(1, line_start)
    end = min(len(lines), line_end)
    if start > end or not lines:
        return ""
    if start == end:
        line = lines[start - 1]
        if char_start is not None and char_end is not None:
            return line[char_start:char_end]
        return line
    parts: list[str] = []
    for line_no in range(start, end + 1):
        line = lines[line_no - 1]
        if line_no == start and char_start is not None:
            parts.append(line[char_start:])
        elif line_no == end and char_end is not None:
            parts.append(line[:char_end])
        else:
            parts.append(line)
    return "\n".join(parts)


def _read_tex(slot_dir: Path) -> str:
    path = slot_dir / TEX_NAME
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _find_comment(data: dict[str, Any], comment_id: str) -> dict[str, Any] | None:
    for item in data.get("comments") or []:
        if isinstance(item, dict) and item.get("id") == comment_id:
            return item
    return None


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def create_comment(
    slot_dir: Path,
    *,
    line_start: int,
    line_end: int,
    body: str,
    author: str = "reviewer",
    char_start: int | None = None,
    char_end: int | None = None,
    selected_text: str | None = None,
) -> dict[str, Any]:
    body = body.strip()
    if not body:
        raise ValueError("Comment body is required")
    if line_start < 1 or line_end < line_start:
        raise ValueError("Invalid line range")

    tex_text = _read_tex(slot_dir)
    anchor: dict[str, Any] = {
        "line_start": line_start,
        "line_end": line_end,
        "content_hash": compute_content_hash(
            tex_text, line_start, line_end, char_start, char_end
        ),
    }
    if char_start is not None:
        anchor["char_start"] = char_start
    if char_end is not None:
        anchor["char_end"] = char_end
    if selected_text:
        anchor["selected_text"] = selected_text

    data = load_comments(slot_dir)
    comment = {
        "id": _new_id("c"),
        "anchor": anchor,
        "resolved": False,
        "created_at": _now_iso(),
        "thread": [
            {
                "id": _new_id("m"),
                "author": author.strip() or "reviewer",
                "body": body,
                "created_at": _now_iso(),
            }
        ],
    }
    data["comments"].append(comment)
    save_comments(slot_dir, data)
    return comment


def add_reply(
    slot_dir: Path,
    comment_id: str,
    *,
    body: str,
    author: str = "reviewer",
) -> dict[str, Any]:
    body = body.strip()
    if not body:
        raise ValueError("Reply body is required")

    data = load_comments(slot_dir)
    comment = _find_comment(data, comment_id)
    if comment is None:
        raise KeyError(comment_id)

    message = {
        "id": _new_id("m"),
        "author": author.strip() or "reviewer",
        "body": body,
        "created_at": _now_iso(),
    }
    thread = comment.setdefault("thread", [])
    if not isinstance(thread, list):
        comment["thread"] = [message]
    else:
        thread.append(message)
    save_comments(slot_dir, data)
    return message


def set_comment_resolved(slot_dir: Path, comment_id: str, *, resolved: bool) -> dict[str, Any]:
    data = load_comments(slot_dir)
    comment = _find_comment(data, comment_id)
    if comment is None:
        raise KeyError(comment_id)
    comment["resolved"] = bool(resolved)
    save_comments(slot_dir, data)
    return comment


def delete_comment(slot_dir: Path, comment_id: str) -> None:
    data = load_comments(slot_dir)
    comments = data.get("comments") or []
    filtered = [item for item in comments if not (isinstance(item, dict) and item.get("id") == comment_id)]
    if len(filtered) == len(comments):
        raise KeyError(comment_id)
    data["comments"] = filtered
    save_comments(slot_dir, data)


def _merge_thread(left: Any, right: Any) -> list[dict[str, Any]]:
    messages: dict[str, dict[str, Any]] = {}
    for item in list(left or []) + list(right or []):
        if isinstance(item, dict) and item.get("id"):
            messages[str(item["id"])] = item
    return list(messages.values())


def merge_comment_stores(
    base: list[Any],
    incoming: list[Any],
    deleted_ids: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Union comments and threads by id; honour explicit deletes from a peer."""
    deleted = {str(item) for item in (deleted_ids or []) if item}
    by_id: dict[str, dict[str, Any]] = {}
    for item in list(base or []) + list(incoming or []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        comment_id = str(item["id"])
        if comment_id in deleted:
            by_id.pop(comment_id, None)
            continue
        existing = by_id.get(comment_id)
        if existing is None:
            by_id[comment_id] = dict(item)
            continue
        merged = {**existing, **item}
        merged["thread"] = _merge_thread(existing.get("thread"), item.get("thread"))
        by_id[comment_id] = merged
    return list(by_id.values())


def apply_comment_merge(
    slot_dir: Path,
    incoming: list[Any],
    deleted_ids: list[Any] | None = None,
) -> dict[str, Any]:
    data = load_comments(slot_dir)
    data["comments"] = merge_comment_stores(data.get("comments") or [], incoming, deleted_ids)
    return save_comments(slot_dir, data)

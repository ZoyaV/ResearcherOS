"""Pull-based live view for running kanban cards (log tail, metrics images)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from koi.adapters.paths import repo_root

LIVE_LOG_RE = re.compile(r"^live_log:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
METRICS_DIR_RE = re.compile(r"^metrics_dir:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
LIVE_NOTE_RE = re.compile(r"^live_note:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
SUBTASK_RE = re.compile(
    r"-\s*\[([ xX])\]\s*([^\n]*?)(?=\s*-\s*\[|$)",
    re.MULTILINE,
)

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"})
MAX_TAIL_BYTES = 256 * 1024
DEFAULT_TAIL_LINES = 100
MAX_TAIL_LINES = 500
MAX_IMAGES = 24


def parse_live_hints(text: str) -> dict[str, str]:
    """Extract live_log, metrics_dir, live_note from card description or report."""
    body = str(text or "")
    out: dict[str, str] = {}
    for key, pattern in (
        ("live_log", LIVE_LOG_RE),
        ("metrics_dir", METRICS_DIR_RE),
        ("live_note", LIVE_NOTE_RE),
    ):
        m = pattern.search(body)
        if m:
            out[key] = m.group(1).strip()
    return out


def parse_subtasks(description: str) -> dict[str, list[str]]:
    open_items: list[str] = []
    done_items: list[str] = []
    body = str(description or "").replace("\\n", "\n")
    for m in SUBTASK_RE.finditer(body):
        text = m.group(2).strip()
        if not text:
            continue
        if m.group(1).lower() == "x":
            done_items.append(text)
        else:
            open_items.append(text)
    return {"open": open_items, "done": done_items}


def _allowed_roots(project_id: str) -> list[Path]:
    repo = repo_root(project_id).resolve()
    return [repo, repo.parent.resolve()]


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_project_path(project_id: str, rel: str) -> Path:
    """Resolve a project-relative path; allow repo and its parent (sibling repos)."""
    raw = str(rel or "").strip()
    if not raw:
        raise ValueError("Empty path")
    if raw.startswith("/"):
        candidate = Path(raw).resolve()
    else:
        candidate = (repo_root(project_id) / raw).resolve()
    for root in _allowed_roots(project_id):
        if _is_under(candidate, root):
            return candidate
    raise ValueError("Path outside project workspace")


def tail_file(path: Path, *, lines: int = DEFAULT_TAIL_LINES) -> str:
    if lines < 1:
        lines = 1
    if lines > MAX_TAIL_LINES:
        lines = MAX_TAIL_LINES
    if not path.is_file():
        raise FileNotFoundError(str(path))
    size = path.stat().st_size
    read_size = min(size, MAX_TAIL_BYTES)
    with path.open("rb") as fh:
        if read_size < size:
            fh.seek(-read_size, 2)
        data = fh.read(read_size)
    text = data.decode("utf-8", errors="replace")
    chunk = text.splitlines()
    if len(chunk) > lines:
        chunk = chunk[-lines:]
    if read_size < size:
        chunk.insert(0, f"… ({size - read_size} bytes omitted) …")
    return "\n".join(chunk)


def list_metric_images(path: Path, *, limit: int = MAX_IMAGES) -> list[dict[str, Any]]:
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    limit = max(1, min(limit, MAX_IMAGES))
    entries: list[tuple[float, Path]] = []
    for child in path.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            entries.append((child.stat().st_mtime, child))
        except OSError:
            continue
    entries.sort(key=lambda item: item[0], reverse=True)
    out: list[dict[str, Any]] = []
    for mtime, child in entries[:limit]:
        out.append(
            {
                "name": child.name,
                "mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
            }
        )
    return out


def _path_for_api(project_id: str, resolved: Path) -> str:
    """Project-relative path for live/file URLs (no ``..``)."""
    repo = repo_root(project_id).resolve()
    try:
        return resolved.resolve().relative_to(repo).as_posix()
    except ValueError:
        for root in _allowed_roots(project_id):
            try:
                return resolved.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
    return str(resolved)


def normalize_hint_path(project_id: str, rel: str) -> str:
    """Strip legacy ``../<repo>/`` prefixes so paths resolve inside the project repo."""
    raw = str(rel or "").strip()
    if not raw or raw.startswith("/"):
        return raw
    repo_name = repo_root(project_id).name
    for prefix in (f"../{repo_name}/", f"{repo_name}/"):
        if raw.startswith(prefix):
            return raw[len(prefix) :]
    return raw


def live_snapshot(
    project_id: str,
    *,
    hints: dict[str, str],
    description: str,
    tail_lines: int = DEFAULT_TAIL_LINES,
) -> dict[str, Any]:
    """Build pull snapshot for UI polling."""
    subtasks = parse_subtasks(description)
    live_log_path = normalize_hint_path(project_id, hints.get("live_log", ""))
    metrics_path = normalize_hint_path(project_id, hints.get("metrics_dir", ""))

    log_block: dict[str, Any] = {"configured": bool(live_log_path), "path": live_log_path}
    metrics_block: dict[str, Any] = {
        "configured": bool(metrics_path),
        "path": metrics_path,
        "images": [],
    }

    if live_log_path:
        try:
            resolved = resolve_project_path(project_id, live_log_path)
            log_block["exists"] = resolved.is_file()
            log_block["resolved_path"] = _path_for_api(project_id, resolved)
            if resolved.is_file():
                log_block["tail"] = tail_file(resolved, lines=tail_lines)
                log_block["size"] = resolved.stat().st_size
        except (ValueError, OSError) as exc:
            log_block["error"] = str(exc)

    if metrics_path:
        try:
            resolved = resolve_project_path(project_id, metrics_path)
            metrics_block["exists"] = resolved.is_dir()
            metrics_block["resolved_path"] = _path_for_api(project_id, resolved)
            if resolved.is_dir():
                metrics_block["images"] = list_metric_images(resolved)
        except (ValueError, OSError) as exc:
            metrics_block["error"] = str(exc)

    return {
        "live_note": hints.get("live_note", ""),
        "subtasks": subtasks,
        "live_log": log_block,
        "metrics_dir": metrics_block,
    }

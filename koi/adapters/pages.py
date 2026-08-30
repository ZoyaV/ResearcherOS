"""Master HTML report pages: koi-structure/pages/<slug>/index.html."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from koi.adapters.paths import pages_dir as project_pages_dir

INDEX_NAME = "index.json"
ENTRY_NAME = "index.html"
MAX_SLUG = 80

EMPTY_HTML = """\
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__TITLE__</title>
  <style>
    body {
      font-family: system-ui, -apple-system, sans-serif;
      max-width: 52rem;
      margin: 2rem auto;
      padding: 0 1.25rem 3rem;
      line-height: 1.55;
      color: #1a1a1a;
      background: #fafafa;
    }
    h1 { font-size: 1.75rem; line-height: 1.2; margin-bottom: 0.75rem; }
    p { color: #445; }
    code { font-size: 0.92em; }
  </style>
</head>
<body>
  <h1>__TITLE__</h1>
  <p>Empty master report. Edit this file in
    <code>koi-structure/pages/__SLUG__/</code>.</p>
</body>
</html>
"""


class PageError(ValueError):
    """Invalid page operation."""


def pages_dir(project_id: str) -> Path:
    d = project_pages_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(project_id: str) -> Path:
    return pages_dir(project_id) / INDEX_NAME


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9_\-]+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"-{2,}", "-", s).strip("-_") or "page"
    if len(s) > MAX_SLUG:
        s = s[:MAX_SLUG].rstrip("-_")
    return s or "page"


def _empty_index() -> dict[str, Any]:
    return {"version": 1, "pages": {}, "attachments": {}}


def load_index(project_id: str) -> dict[str, Any]:
    path = _index_path(project_id)
    if not path.exists():
        index = _empty_index()
        _discover_orphans(project_id, index)
        return index
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        index = _empty_index()
        _discover_orphans(project_id, index)
        return index
    if not isinstance(data, dict):
        index = _empty_index()
        _discover_orphans(project_id, index)
        return index
    pages = data.get("pages")
    attachments = data.get("attachments")
    if not isinstance(pages, dict):
        pages = {}
    if not isinstance(attachments, dict):
        attachments = {}
    index = {"version": 1, "pages": pages, "attachments": attachments}
    _discover_orphans(project_id, index)
    return index


def save_index(project_id: str, index: dict[str, Any]) -> None:
    path = _index_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "pages": index.get("pages") or {},
        "attachments": index.get("attachments") or {},
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _discover_orphans(project_id: str, index: dict[str, Any]) -> None:
    """Register folders under pages/ that have index.html but no index entry."""
    root = pages_dir(project_id)
    known_slugs = {
        str(meta.get("slug") or "")
        for meta in (index.get("pages") or {}).values()
        if isinstance(meta, dict)
    }
    changed = False
    for child in sorted(root.iterdir() if root.is_dir() else []):
        if not child.is_dir() or child.name.startswith("."):
            continue
        entry = child / ENTRY_NAME
        if not entry.is_file() or child.name in known_slugs:
            continue
        page_id = str(uuid4())
        title = _title_from_html(entry) or child.name
        index.setdefault("pages", {})[page_id] = {
            "id": page_id,
            "title": title,
            "slug": child.name,
            "entry": ENTRY_NAME,
            "created_at": _now(),
            "updated_at": _now(),
        }
        known_slugs.add(child.name)
        changed = True
    if changed:
        save_index(project_id, index)


def _title_from_html(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def _unique_slug(project_id: str, base: str, index: dict[str, Any]) -> str:
    used = {
        str(meta.get("slug") or "")
        for meta in (index.get("pages") or {}).values()
        if isinstance(meta, dict)
    }
    root = pages_dir(project_id)
    for child in root.iterdir() if root.is_dir() else []:
        if child.is_dir():
            used.add(child.name)
    candidate = base
    n = 2
    while candidate in used or (root / candidate).exists():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def list_pages(project_id: str) -> list[dict[str, Any]]:
    index = load_index(project_id)
    pages = []
    for page_id, meta in (index.get("pages") or {}).items():
        if not isinstance(meta, dict):
            continue
        item = dict(meta)
        item["id"] = str(meta.get("id") or page_id)
        pages.append(item)
    pages.sort(key=lambda p: (str(p.get("title") or "").lower(), p["id"]))
    return pages


def get_page(project_id: str, page_id: str) -> dict[str, Any] | None:
    index = load_index(project_id)
    meta = (index.get("pages") or {}).get(page_id)
    if not isinstance(meta, dict):
        return None
    out = dict(meta)
    out["id"] = str(meta.get("id") or page_id)
    return out


def page_dir(project_id: str, page_id: str) -> Path | None:
    meta = get_page(project_id, page_id)
    if meta is None:
        return None
    slug = str(meta.get("slug") or "").strip()
    if not slug or ".." in Path(slug).parts:
        return None
    path = (pages_dir(project_id) / slug).resolve()
    root = pages_dir(project_id).resolve()
    if not str(path).startswith(str(root) + "/") and path != root:
        return None
    return path if path.is_dir() else None


def resolve_page_file(project_id: str, page_id: str, relative: str = ENTRY_NAME) -> Path | None:
    base = page_dir(project_id, page_id)
    if base is None:
        return None
    rel = (relative or ENTRY_NAME).strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    target = (base / rel).resolve()
    if not str(target).startswith(str(base.resolve()) + "/") and target != base.resolve():
        return None
    return target if target.is_file() else None


def create_page(project_id: str, title: str) -> dict[str, Any]:
    title = (title or "").strip() or "Master report"
    index = load_index(project_id)
    slug = _unique_slug(project_id, slugify(title), index)
    page_id = str(uuid4())
    folder = pages_dir(project_id) / slug
    folder.mkdir(parents=True, exist_ok=False)
    html = EMPTY_HTML.replace("__TITLE__", title).replace("__SLUG__", slug)
    (folder / ENTRY_NAME).write_text(html, encoding="utf-8")
    meta = {
        "id": page_id,
        "title": title,
        "slug": slug,
        "entry": ENTRY_NAME,
        "created_at": _now(),
        "updated_at": _now(),
    }
    index.setdefault("pages", {})[page_id] = meta
    save_index(project_id, index)
    return dict(meta)


def delete_page(project_id: str, page_id: str) -> None:
    import shutil

    index = load_index(project_id)
    meta = (index.get("pages") or {}).pop(page_id, None)
    if meta is None:
        raise PageError("Page not found")
    attachments = index.setdefault("attachments", {})
    for node_id, items in list(attachments.items()):
        if not isinstance(items, list):
            continue
        filtered = [
            item
            for item in items
            if isinstance(item, dict) and item.get("page_id") != page_id
        ]
        if filtered:
            attachments[node_id] = filtered
        else:
            attachments.pop(node_id, None)
    save_index(project_id, index)
    slug = str((meta or {}).get("slug") or "")
    if slug and ".." not in Path(slug).parts:
        folder = pages_dir(project_id) / slug
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)


def attachments_for_node(project_id: str, node_id: str) -> list[dict[str, Any]]:
    index = load_index(project_id)
    pages = index.get("pages") or {}
    raw = (index.get("attachments") or {}).get(node_id) or []
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        page_id = str(item.get("page_id") or "")
        meta = pages.get(page_id)
        if not isinstance(meta, dict):
            continue
        out.append(
            {
                "page_id": page_id,
                "visible": bool(item.get("visible")),
                "title": str(meta.get("title") or meta.get("slug") or page_id),
                "slug": str(meta.get("slug") or ""),
            }
        )
    return out


def attach_page(
    project_id: str,
    node_id: str,
    page_id: str,
    *,
    visible: bool = False,
) -> list[dict[str, Any]]:
    index = load_index(project_id)
    if page_id not in (index.get("pages") or {}):
        raise PageError("Page not found")
    items = list((index.get("attachments") or {}).get(node_id) or [])
    cleaned: list[dict[str, Any]] = []
    found = False
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("page_id") == page_id:
            cleaned.append({"page_id": page_id, "visible": bool(visible)})
            found = True
        else:
            cleaned.append(
                {
                    "page_id": str(item.get("page_id")),
                    "visible": bool(item.get("visible")),
                }
            )
    if not found:
        cleaned.append({"page_id": page_id, "visible": bool(visible)})
    index.setdefault("attachments", {})[node_id] = cleaned
    save_index(project_id, index)
    return attachments_for_node(project_id, node_id)


def detach_page(project_id: str, node_id: str, page_id: str) -> list[dict[str, Any]]:
    index = load_index(project_id)
    attachments = index.setdefault("attachments", {})
    items = attachments.get(node_id) or []
    if not isinstance(items, list):
        items = []
    filtered = [
        item
        for item in items
        if isinstance(item, dict) and item.get("page_id") != page_id
    ]
    if filtered:
        attachments[node_id] = filtered
    else:
        attachments.pop(node_id, None)
    save_index(project_id, index)
    return attachments_for_node(project_id, node_id)


def set_page_visible(
    project_id: str,
    node_id: str,
    page_id: str,
    visible: bool,
) -> list[dict[str, Any]]:
    index = load_index(project_id)
    attachments = index.setdefault("attachments", {})
    items = attachments.get(node_id) or []
    if not isinstance(items, list):
        raise PageError("Attachment not found")
    found = False
    updated: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("page_id") == page_id:
            updated.append({"page_id": page_id, "visible": bool(visible)})
            found = True
        else:
            updated.append(
                {
                    "page_id": str(item.get("page_id")),
                    "visible": bool(item.get("visible")),
                }
            )
    if not found:
        raise PageError("Attachment not found")
    attachments[node_id] = updated
    save_index(project_id, index)
    return attachments_for_node(project_id, node_id)


def visible_pins_from_index(index: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Build map pins from a pages ``index.json`` payload (no project mount)."""
    pages = index.get("pages") or {}
    pins: dict[str, list[dict[str, str]]] = {}
    if not isinstance(pages, dict):
        return pins
    for node_id, items in (index.get("attachments") or {}).items():
        if not isinstance(items, list):
            continue
        visible: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("visible"):
                continue
            page_id = str(item.get("page_id") or "")
            meta = pages.get(page_id)
            if not isinstance(meta, dict):
                continue
            visible.append(
                {
                    "id": page_id,
                    "title": str(meta.get("title") or meta.get("slug") or page_id),
                }
            )
        if visible:
            pins[str(node_id)] = visible
    return pins


def load_index_from_pages_root(pages_root: Path) -> dict[str, Any]:
    """Read ``pages/index.json`` from a koi-structure tree (Hub sync temp dir)."""
    path = pages_root / INDEX_NAME
    if not path.is_file():
        return _empty_index()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_index()
    if not isinstance(data, dict):
        return _empty_index()
    pages = data.get("pages")
    attachments = data.get("attachments")
    return {
        "version": 1,
        "pages": pages if isinstance(pages, dict) else {},
        "attachments": attachments if isinstance(attachments, dict) else {},
    }


def visible_pins_from_pages_root(pages_root: Path) -> dict[str, list[dict[str, str]]]:
    """node_id → visible pages using an on-disk ``pages/`` directory."""
    return visible_pins_from_index(load_index_from_pages_root(pages_root))


def visible_pins(project_id: str) -> dict[str, list[dict[str, str]]]:
    """node_id → visible pages for map icons."""
    return visible_pins_from_index(load_index(project_id))


def list_pages_for_docs(project_id: str) -> list[dict[str, Any]]:
    """Pages listed in knowledge/docs dashboard."""
    return [
        {
            "id": page["id"],
            "title": page.get("title") or page.get("slug") or page["id"],
            "slug": page.get("slug") or "",
            "path": f"pages/{page.get('slug')}/{page.get('entry') or ENTRY_NAME}",
        }
        for page in list_pages(project_id)
    ]

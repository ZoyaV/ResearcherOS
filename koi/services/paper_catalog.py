"""Discover and resolve per-project paper slots under ``koi-structure/paper/``.

Layout::

    paper/                          # legacy single paper (slug ``default``)
      main.tex
      paper.pdf
      status.json
    paper/<slug>/                   # additional or standalone papers
      paper.json                    # optional metadata (title, description)
      main.tex
      paper.pdf
      status.json
      figures/
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from koi.adapters.paths import paper_dir

DEFAULT_PAPER_SLUG = "default"
META_NAME = "paper.json"
STATUS_NAME = "status.json"
TEX_NAME = "main.tex"
PDF_NAME = "paper.pdf"
RUNNING_STALE_S = 45 * 60
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def normalize_paper_slug(slug: str | None) -> str:
    raw = (slug or DEFAULT_PAPER_SLUG).strip().lower()
    if not raw:
        return DEFAULT_PAPER_SLUG
    if not SLUG_RE.fullmatch(raw):
        raise ValueError(f"Invalid paper slug: {slug!r}")
    return raw


def _humanize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def find_pdf(slot_dir: Path) -> Path | None:
    preferred = slot_dir / PDF_NAME
    if preferred.is_file():
        return preferred
    main_pdf = slot_dir / "main.pdf"
    if main_pdf.is_file():
        return main_pdf
    pdfs = sorted(
        p for p in slot_dir.glob("*.pdf") if p.is_file() and not p.name.startswith(".")
    )
    return pdfs[0] if len(pdfs) == 1 else None


def dir_has_paper_artifacts(path: Path) -> bool:
    """True when the slot has real content (not a lone stale status.json)."""
    if (path / TEX_NAME).is_file() or (path / META_NAME).is_file():
        return True
    return find_pdf(path) is not None


def _is_running(status: dict) -> bool:
    if status.get("state") != "running":
        return False
    started = status.get("started_at", "")
    try:
        dt = datetime.fromisoformat(started)
    except (TypeError, ValueError):
        return False
    return (datetime.now(timezone.utc) - dt).total_seconds() < RUNNING_STALE_S


def _normalize_paper_state(status: dict, *, pdf_exists: bool) -> tuple[str, str | None]:
    state = status.get("state")
    if not state:
        state = "done" if pdf_exists else "none"
    error = status.get("error")
    if state == "running" and not _is_running(status):
        state = "error"
        error = error or "Генерация прервана (устаревший running-статус)."
    return str(state), error


def read_paper_meta(slot_dir: Path) -> dict[str, Any]:
    return _read_json(slot_dir / META_NAME)


def read_paper_status(slot_dir: Path) -> dict[str, Any]:
    return _read_json(slot_dir / STATUS_NAME)


def _default_title(slug: str) -> str:
    if slug == DEFAULT_PAPER_SLUG:
        return "Основная статья"
    return _humanize_slug(slug)


def paper_entry(project_id: str, slug: str, slot_dir: Path) -> dict[str, Any]:
    meta = read_paper_meta(slot_dir)
    status = read_paper_status(slot_dir)
    pdf = find_pdf(slot_dir)
    tex = slot_dir / TEX_NAME
    pdf_exists = pdf is not None
    title = str(meta.get("title") or "").strip() or _default_title(slug)
    state, error = _normalize_paper_state(status, pdf_exists=pdf_exists)
    out: dict[str, Any] = {
        "slug": slug,
        "title": title,
        "description": str(meta.get("description") or "").strip(),
        "state": state,
        "started_at": status.get("started_at"),
        "finished_at": status.get("finished_at"),
        "backend": status.get("backend"),
        "engine": status.get("engine"),
        "mode": status.get("mode"),
        "error": error,
        "log_tail": status.get("log_tail"),
        "pdf_exists": pdf_exists,
        "tex_exists": tex.is_file(),
        "path": str(slot_dir.relative_to(paper_dir(project_id))),
    }
    if pdf_exists and pdf is not None:
        out["pdf_mtime"] = datetime.fromtimestamp(
            pdf.stat().st_mtime, tz=timezone.utc
        ).isoformat(timespec="seconds")
    return out


def list_project_papers(project_id: str) -> list[dict[str, Any]]:
    root = paper_dir(project_id)
    if not root.is_dir():
        return []

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    if dir_has_paper_artifacts(root):
        entries.append(paper_entry(project_id, DEFAULT_PAPER_SLUG, root))
        seen.add(DEFAULT_PAPER_SLUG)

    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in seen:
            continue
        if dir_has_paper_artifacts(child):
            entries.append(paper_entry(project_id, child.name, child))
            seen.add(child.name)

    return entries


def get_paper_slot_dir(project_id: str, slug: str | None = None) -> Path | None:
    """Resolve an existing on-disk slot directory, or ``None`` if absent."""
    slug = normalize_paper_slug(slug)
    root = paper_dir(project_id)
    if slug == DEFAULT_PAPER_SLUG:
        if dir_has_paper_artifacts(root):
            return root
        nested = root / DEFAULT_PAPER_SLUG
        if nested.is_dir() and dir_has_paper_artifacts(nested):
            return nested
        return None

    candidate = root / slug
    if candidate.is_dir() and dir_has_paper_artifacts(candidate):
        return candidate
    return None


def prepare_paper_slot_dir(project_id: str, slug: str | None = None) -> Path:
    """Directory for writing a paper slot (creates parents)."""
    slug = normalize_paper_slug(slug)
    root = paper_dir(project_id)
    if slug == DEFAULT_PAPER_SLUG:
        legacy = get_paper_slot_dir(project_id, DEFAULT_PAPER_SLUG)
        if legacy is not None and legacy == root:
            root.mkdir(parents=True, exist_ok=True)
            return root
        if legacy is not None:
            return legacy
        root.mkdir(parents=True, exist_ok=True)
        return root
    slot = root / slug
    slot.mkdir(parents=True, exist_ok=True)
    return slot


def ensure_paper_slug(project_id: str, slug: str | None = None) -> str:
    slug = normalize_paper_slug(slug)
    papers = list_project_papers(project_id)
    known = {item["slug"] for item in papers}
    if slug in known or slug == DEFAULT_PAPER_SLUG:
        return slug
    if papers:
        raise KeyError(f"Paper slot not found: {slug}")
    return slug

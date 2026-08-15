"""Deterministic document / room identifiers."""

from __future__ import annotations

import hashlib
import re

_SLUG_SAFE = re.compile(r"[^A-Za-z0-9._/-]+")


def document_id(
    repository_id: str,
    paper_id: str,
    relative_file_path: str = "main.tex",
) -> str:
    repo = (repository_id or "").strip()
    paper = (paper_id or "").strip()
    path = (relative_file_path or "main.tex").strip().lstrip("/")
    if not repo or not paper:
        raise ValueError("repository_id and paper_id are required")
    return f"{repo}:{paper}:{path}"


def room_id(
    repository_id: str,
    paper_id: str,
    relative_file_path: str = "main.tex",
) -> str:
    raw = document_id(repository_id, paper_id, relative_file_path)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def session_key(project_id: str, slug: str) -> str:
    return f"{(project_id or '').strip()}:{(slug or '').strip()}"


def safe_relpath(path: str) -> str:
    cleaned = _SLUG_SAFE.sub("-", (path or "main.tex").strip())
    return cleaned or "main.tex"

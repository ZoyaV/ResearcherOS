"""Load a KOI project from a directory tree (no local project mount)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from koi.adapters.research_store import _record_to_question, apply_research_to_project
from koi.core.md_io import parse_project_md
from koi.core.models import MethodResearchQuestion, Project
from koi.projects.views import project_to_client


def read_koi_meta(koi_root: Path) -> dict[str, Any]:
    project_md = koi_root / "project.md"
    if not project_md.exists():
        return {}
    text = project_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    parsed = yaml.safe_load(parts[1]) or {}
    return parsed if isinstance(parsed, dict) else {}


def load_project_from_koi_root(koi_root: Path) -> Optional[Project]:
    project_md = koi_root / "project.md"
    if not project_md.exists():
        return None
    text = project_md.read_text(encoding="utf-8")
    meta = read_koi_meta(koi_root)
    project_id = str(meta.get("id") or koi_root.name)
    project = parse_project_md(text, project_id=project_id)
    research_file = koi_root / "research.json"
    if research_file.exists():
        data = json.loads(research_file.read_text(encoding="utf-8"))
        by_method: dict[str, list[MethodResearchQuestion]] = {}
        raw = data.get("questions") if isinstance(data, dict) else None
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                method_id = str(item.get("method_id") or "").strip()
                if not method_id:
                    continue
                q = _record_to_question(item)
                if q is None:
                    continue
                by_method.setdefault(method_id, []).append(q)
        apply_research_to_project(project, by_method)
    return project


def project_snapshot(koi_root: Path) -> Optional[dict]:
    project = load_project_from_koi_root(koi_root)
    if project is None:
        return None
    return project_to_client(project)

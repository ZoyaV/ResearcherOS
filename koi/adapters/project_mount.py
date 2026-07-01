"""Discover KOI projects via ``<repo>/koi-structure/project.md``."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent

log = logging.getLogger(__name__)

KOI_STRUCTURE_DIR = "koi-structure"
PROJECT_MD = "project.md"

_SKIP_DIR_NAMES = frozenset(
    {
        "ReseachOS",
        "koi-workspace",
        "node_modules",
        ".venv",
        ".git",
        ".tools",
    }
)


DEFAULT_SYNC_BRANCH = "koi/research"
WORKTREE_DIR = ".koi-sync-worktree"
BOOTSTRAP_WORKTREE_DIR = ".koi-sync-bootstrap"


@dataclass(frozen=True)
class ProjectMount:
    project_id: str
    repo_root: Path
    koi_root: Path
    code_root: Path
    programs: tuple[str, ...]
    git_repo: bool = False
    git_sync_branch: str | None = None


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    return meta, parts[2].lstrip("\n")


def _parse_programs(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            pid = item.get("id")
            if pid:
                out.append(str(pid))
        elif item:
            out.append(str(item))
    return tuple(out)


def _resolve_code_root(repo_root: Path, koi_root: Path, meta: dict[str, Any]) -> Path:
    raw = meta.get("code_root")
    if raw:
        p = Path(str(raw))
        if p.is_absolute():
            return p.resolve()
        return (koi_root / p).resolve()
    projectcode = repo_root / "projectcode"
    if projectcode.is_dir():
        return projectcode.resolve()
    return repo_root.resolve()


def scan_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    default = ENGINE_ROOT.parent.resolve()
    roots.append(default)
    extra = os.environ.get("KOI_SCAN_ROOTS", "").strip()
    if extra:
        for part in extra.split(","):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen and root.is_dir():
            seen.add(root)
            unique.append(root)
    return tuple(unique)


def _iter_repo_candidates(root: Path) -> list[Path]:
    if root.resolve() == ENGINE_ROOT.resolve():
        return []
    out: list[Path] = []
    try:
        children = sorted(root.iterdir())
    except OSError:
        return out
    for child in children:
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith(".") or name in _SKIP_DIR_NAMES:
            continue
        if child.resolve() == ENGINE_ROOT.resolve():
            continue
        out.append(child)
    return out


def _parse_git_repo(meta: dict[str, Any]) -> bool:
    raw = meta.get("git_repo")
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _parse_git_sync_branch(meta: dict[str, Any], *, git_repo: bool) -> str | None:
    if not git_repo:
        return None
    raw = meta.get("git_sync_branch")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return DEFAULT_SYNC_BRANCH


def discover_projects() -> list[ProjectMount]:
    mounts: dict[str, ProjectMount] = {}
    for root in scan_roots():
        for repo_root in _iter_repo_candidates(root):
            koi_root = repo_root / KOI_STRUCTURE_DIR
            md_path = koi_root / PROJECT_MD
            if not md_path.is_file():
                continue
            try:
                text = md_path.read_text(encoding="utf-8")
            except OSError as exc:
                log.warning("Cannot read %s: %s", md_path, exc)
                continue
            meta, _ = _split_frontmatter(text)
            project_id = str(meta.get("id") or repo_root.name)
            if project_id in mounts:
                log.warning(
                    "Duplicate project id %r (%s vs %s); keeping first",
                    project_id,
                    mounts[project_id].repo_root,
                    repo_root,
                )
                continue
            git_repo = _parse_git_repo(meta)
            mounts[project_id] = ProjectMount(
                project_id=project_id,
                repo_root=repo_root.resolve(),
                koi_root=koi_root.resolve(),
                code_root=_resolve_code_root(repo_root, koi_root, meta),
                programs=_parse_programs(meta.get("programs")),
                git_repo=git_repo,
                git_sync_branch=_parse_git_sync_branch(meta, git_repo=git_repo),
            )
    return sorted(mounts.values(), key=lambda m: m.project_id)


@lru_cache(maxsize=1)
def _mount_index() -> dict[str, ProjectMount]:
    return {m.project_id: m for m in discover_projects()}


def rescan_projects() -> None:
    """Clear cached discovery (call after creating or attaching a project)."""
    _mount_index.cache_clear()


def list_mounts() -> list[ProjectMount]:
    return sorted(_mount_index().values(), key=lambda m: m.project_id)


def get_mount(project_id: str) -> ProjectMount | None:
    return _mount_index().get(project_id)


def get_mount_or_raise(project_id: str) -> ProjectMount:
    mount = get_mount(project_id)
    if mount is None:
        raise KeyError(f"Project not found: {project_id}")
    return mount


def repo_folder_name(title: str) -> str:
    """Filesystem folder name for a new project repo (sibling of engine)."""
    s = title.strip()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:48] or "project").lower()

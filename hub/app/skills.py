"""Extract publishable skills from ``koi-structure/skills/`` (git as source of truth).

v1 rules:
- Required per skill dir: ``manifest.yaml`` + ``README.md``
- Only ``visibility: public`` skills are eligible
- Hub publishes them only when the parent project is Hub-``public`` and enabled
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

_SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MAX_FILE_BYTES = 512_000
_SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", "node_modules"}


@dataclass
class ParsedSkill:
    id: str
    title: str
    summary: str
    visibility: str
    readme_md: str
    skill_md: str = ""
    # relative path → utf-8 text (for zip download / listing)
    file_contents: dict[str, str] = field(default_factory=dict)
    errors: list[str] | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def skill_key(project_slug: str, skill_id: str) -> str:
    return f"{project_slug}/{skill_id}"


def _load_manifest(path: Path) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — surface as skill error
        return None, f"invalid YAML: {exc}"
    if not isinstance(raw, dict):
        return None, "manifest must be a mapping"
    return raw, None


def _collect_text_files(skill_dir: Path) -> dict[str, str]:
    """Read text files under the skill dir (relative posix paths)."""
    out: dict[str, str] = {}
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(skill_dir).parts
        if any(p in _SKIP_DIR_NAMES or p.startswith(".") for p in rel_parts):
            continue
        if path.stat().st_size > _MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        out[path.relative_to(skill_dir).as_posix()] = text
    return out


def parse_skill_dir(skill_dir: Path) -> ParsedSkill:
    """Parse one ``skills/<id>/`` directory. Always returns a ParsedSkill."""
    folder_id = skill_dir.name
    errors: list[str] = []

    manifest_path = skill_dir / "manifest.yaml"
    if not manifest_path.is_file():
        alt = skill_dir / "manifest.yml"
        if alt.is_file():
            manifest_path = alt
        else:
            errors.append("missing manifest.yaml")

    readme_path = skill_dir / "README.md"
    if not readme_path.is_file():
        errors.append("missing README.md")

    manifest: dict[str, Any] = {}
    if "missing manifest.yaml" not in errors:
        loaded, err = _load_manifest(manifest_path)
        if err:
            errors.append(err)
        else:
            assert loaded is not None
            manifest = loaded

    skill_id = str(manifest.get("id") or folder_id).strip()
    if skill_id != folder_id:
        errors.append(f"manifest id {skill_id!r} must match folder name {folder_id!r}")
    if not _SKILL_ID_RE.match(skill_id):
        errors.append(
            "id must match ^[a-z0-9][a-z0-9._-]{0,63}$ "
            f"(got {skill_id!r})"
        )

    visibility = str(manifest.get("visibility") or "private").strip().lower()
    if visibility not in {"public", "private"}:
        errors.append("visibility must be public or private")

    title = str(manifest.get("title") or skill_id).strip() or skill_id
    summary = str(manifest.get("summary") or "").strip()

    readme_md = ""
    if "missing README.md" not in errors:
        readme_md = readme_path.read_text(encoding="utf-8")
        if not readme_md.strip():
            errors.append("README.md is empty")

    skill_md = ""
    skill_md_path = skill_dir / "SKILL.md"
    if skill_md_path.is_file():
        skill_md = skill_md_path.read_text(encoding="utf-8")

    file_contents = _collect_text_files(skill_dir) if skill_dir.is_dir() else {}

    return ParsedSkill(
        id=skill_id,
        title=title,
        summary=summary,
        visibility=visibility,
        readme_md=readme_md,
        skill_md=skill_md,
        file_contents=file_contents,
        errors=errors or None,
    )


def extract_skills(koi_root: Path) -> list[ParsedSkill]:
    """Return all skill dirs under ``koi_root/skills/`` (valid and invalid)."""
    root = koi_root / "skills"
    if not root.is_dir():
        return []
    out: list[ParsedSkill] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        out.append(parse_skill_dir(child))
    return out


def public_skills_for_publish(koi_root: Path) -> list[ParsedSkill]:
    """Skills eligible for the Hub pool: valid + ``visibility: public``."""
    return [
        s
        for s in extract_skills(koi_root)
        if s.ok and s.visibility == "public"
    ]


def files_manifest(file_contents: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"path": path, "size": len(content.encode("utf-8"))}
        for path, content in sorted(file_contents.items())
    ]


def skill_to_entry(
    skill: ParsedSkill,
    *,
    project_slug: str,
    project_title: str,
    owner_login: str,
    repo_full_name: str,
    branch: str,
    synced_at: str,
) -> dict[str, Any]:
    key = skill_key(project_slug, skill.id)
    contents = dict(skill.file_contents)
    if skill.readme_md and "README.md" not in contents:
        contents["README.md"] = skill.readme_md
    if skill.skill_md and "SKILL.md" not in contents:
        contents["SKILL.md"] = skill.skill_md
    return {
        "key": key,
        "id": skill.id,
        "title": skill.title,
        "summary": skill.summary,
        "visibility": skill.visibility,
        "readme_md": skill.readme_md,
        "skill_md": skill.skill_md,
        "has_skill_md": bool(skill.skill_md.strip()),
        "files": files_manifest(contents),
        "file_contents": contents,
        "project_slug": project_slug,
        "project_title": project_title,
        "owner_login": owner_login,
        "repo_full_name": repo_full_name,
        "branch": branch,
        "synced_at": synced_at,
        "view_url": f"/skills/{project_slug}/{skill.id}",
        "download_url": f"/api/skills/{project_slug}/{skill.id}/download",
        "project_url": f"/p/{project_slug}",
    }


def skill_public_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """API payload for the skill page — no raw file bodies."""
    files = entry.get("files")
    if not isinstance(files, list):
        files = []
    if not files:
        if entry.get("file_contents") and isinstance(entry["file_contents"], dict):
            files = files_manifest(entry["file_contents"])
        else:
            if entry.get("readme_md"):
                files.append(
                    {
                        "path": "README.md",
                        "size": len(str(entry["readme_md"]).encode("utf-8")),
                    }
                )
            if entry.get("skill_md"):
                files.append(
                    {
                        "path": "SKILL.md",
                        "size": len(str(entry["skill_md"]).encode("utf-8")),
                    }
                )
    return {
        "key": entry.get("key"),
        "id": entry.get("id"),
        "title": entry.get("title"),
        "summary": entry.get("summary") or "",
        "visibility": entry.get("visibility") or "public",
        "readme_md": entry.get("readme_md") or "",
        "has_skill_md": bool(entry.get("has_skill_md") or entry.get("skill_md")),
        "files": files,
        "project_slug": entry.get("project_slug"),
        "project_title": entry.get("project_title") or "",
        "owner_login": entry.get("owner_login") or "",
        "repo_full_name": entry.get("repo_full_name") or "",
        "branch": entry.get("branch") or "",
        "synced_at": entry.get("synced_at") or "",
        "view_url": entry.get("view_url") or "",
        "download_url": entry.get("download_url")
        or f"/api/skills/{entry.get('project_slug')}/{entry.get('id')}/download",
        "project_url": entry.get("project_url") or "",
    }


def skill_file_contents_for_download(entry: dict[str, Any]) -> dict[str, str]:
    raw = entry.get("file_contents")
    if isinstance(raw, dict) and raw:
        return {str(k): str(v) for k, v in raw.items()}
    out: dict[str, str] = {}
    if entry.get("readme_md"):
        out["README.md"] = str(entry["readme_md"])
    if entry.get("skill_md"):
        out["SKILL.md"] = str(entry["skill_md"])
    skill_id = str(entry.get("id") or "skill")
    if "manifest.yaml" not in out:
        out["manifest.yaml"] = (
            f"id: {skill_id}\n"
            f"title: {entry.get('title') or skill_id}\n"
            f"summary: {entry.get('summary') or ''}\n"
            f"visibility: {entry.get('visibility') or 'public'}\n"
        )
    return out


def skill_summary(entry: dict[str, Any]) -> dict[str, Any]:
    """Catalog row without large markdown bodies."""
    return {
        "key": entry["key"],
        "id": entry["id"],
        "title": entry["title"],
        "summary": entry.get("summary") or "",
        "project_slug": entry["project_slug"],
        "project_title": entry.get("project_title") or "",
        "owner_login": entry.get("owner_login") or "",
        "repo_full_name": entry.get("repo_full_name") or "",
        "synced_at": entry.get("synced_at") or "",
        "has_skill_md": bool(entry.get("has_skill_md")),
        "files_count": len(entry.get("files") or []),
        "view_url": entry.get("view_url") or "",
        "download_url": entry.get("download_url") or "",
        "project_url": entry.get("project_url") or "",
    }

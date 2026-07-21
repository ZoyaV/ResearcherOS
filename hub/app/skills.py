"""Extract publishable skills from ``koi-structure/skills/`` (git as source of truth).

v1 rules:
- Required per skill dir: ``manifest.yaml`` + ``README.md``
- Only ``visibility: public`` skills are eligible
- Hub publishes them only when the parent project is Hub-``public`` and enabled
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

_SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


@dataclass
class ParsedSkill:
    id: str
    title: str
    summary: str
    visibility: str
    readme_md: str
    skill_md: str = ""
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


def parse_skill_dir(skill_dir: Path) -> ParsedSkill:
    """Parse one ``skills/<id>/`` directory. Always returns a ParsedSkill."""
    folder_id = skill_dir.name
    errors: list[str] = []

    manifest_path = skill_dir / "manifest.yaml"
    if not manifest_path.is_file():
        # also accept .yml
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

    return ParsedSkill(
        id=skill_id,
        title=title,
        summary=summary,
        visibility=visibility,
        readme_md=readme_md,
        skill_md=skill_md,
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
    return {
        "key": key,
        "id": skill.id,
        "title": skill.title,
        "summary": skill.summary,
        "visibility": skill.visibility,
        "readme_md": skill.readme_md,
        "skill_md": skill.skill_md,
        "has_skill_md": bool(skill.skill_md.strip()),
        "project_slug": project_slug,
        "project_title": project_title,
        "owner_login": owner_login,
        "repo_full_name": repo_full_name,
        "branch": branch,
        "synced_at": synced_at,
        "view_url": f"/skills/{project_slug}/{skill.id}",
        "project_url": f"/p/{project_slug}",
    }


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
        "view_url": entry.get("view_url") or "",
        "project_url": entry.get("project_url") or "",
    }

"""Research program helpers for Hub snapshots."""

from __future__ import annotations

from typing import Any

from hub.app.store import HubProject
from koi.laboratory.programs import parse_program_entries


def hub_project_programs(
    hub_project: HubProject,
    *,
    snapshot: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Programs declared on the Hub project, with snapshot meta as fallback."""
    programs = list(hub_project.programs or [])
    if programs:
        return programs
    if not snapshot:
        return []
    meta = snapshot.get("meta") if isinstance(snapshot.get("meta"), dict) else {}
    return parse_program_entries(meta.get("programs") if isinstance(meta, dict) else None)


def program_ids(programs: list[dict[str, str]]) -> list[str]:
    return [p["id"] for p in programs if p.get("id")]

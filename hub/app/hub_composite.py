"""Composite (merged) hypothesis trees for Hub snapshots."""

from __future__ import annotations

import re
from typing import Any, Optional

from hub.app.client_project import project_from_client
from hub.app.hub_programs import hub_project_programs, program_ids
from hub.app.store import HubProject, HubStore
from koi.projects.composites import (
    build_composite,
    composite_to_client,
    normalize_node_title,
)

AUTO_COMPOSITE_PREFIX = "auto-problem:"


def _normalize_title(value: str) -> str:
    return normalize_node_title(value)


def _problem_title(project: dict[str, Any]) -> Optional[str]:
    for node in project.get("nodes") or []:
        if node.get("node_type") == "problem":
            title = str(node.get("title") or "").strip()
            if title:
                return title
    return None


def _problem_key(project: dict[str, Any]) -> Optional[str]:
    title = _problem_title(project)
    if not title:
        return None
    normalized = _normalize_title(title)
    return normalized or None


def _auto_composite_id(problem_key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", problem_key).strip("-")[:48] or "problem"
    return f"{AUTO_COMPOSITE_PREFIX}{slug}"


def _explicit_composite_id(hub_project: HubProject) -> str:
    return (hub_project.composite_id or "").strip()


def _group_key(hub_project: HubProject, project: dict[str, Any]) -> Optional[str]:
    """Internal grouping key: prefer shared problem title over explicit id.

    Explicit ``composite_id`` alone used to split trees when one member had
    ``llm-ood-decision-making`` and another only auto ``auto-problem:…`` for the
    same problem text. Problem-title grouping keeps those together.
    """
    problem = _problem_key(project)
    if problem:
        return f"problem:{problem}"
    explicit = _explicit_composite_id(hub_project)
    if explicit:
        return f"explicit:{explicit}"
    return None


def _public_composite_id(
    group_key: str, group: list[tuple[HubProject, dict[str, Any]]]
) -> str:
    explicits = sorted(
        {
            _explicit_composite_id(hub_project)
            for hub_project, _project in group
            if _explicit_composite_id(hub_project)
        }
    )
    if explicits:
        return explicits[0]
    if group_key.startswith("problem:"):
        return _auto_composite_id(group_key[len("problem:") :])
    if group_key.startswith("explicit:"):
        return group_key[len("explicit:") :]
    return group_key


def _composite_groups(
    members: list[tuple[HubProject, dict[str, Any]]],
) -> dict[str, list[tuple[HubProject, dict[str, Any]]]]:
    """Map public composite_id → member list (≥2 distinct project ids)."""
    raw: dict[str, list[tuple[HubProject, dict[str, Any]]]] = {}
    for hub_project, project in members:
        key = _group_key(hub_project, project)
        if not key:
            continue
        raw.setdefault(key, []).append((hub_project, project))

    out: dict[str, list[tuple[HubProject, dict[str, Any]]]] = {}
    for group_key, group in raw.items():
        member_ids = {str(project.get("id") or "") for _, project in group}
        member_ids.discard("")
        if len(member_ids) < 2:
            continue
        public_id = _public_composite_id(group_key, group)
        # Same public id from two problem groups is unlikely; last write wins merge.
        if public_id in out:
            out[public_id].extend(group)
        else:
            out[public_id] = list(group)
    return out


def list_hub_composites(
    members: list[tuple[HubProject, dict[str, Any]]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for composite_id, group in _composite_groups(members).items():
        member_ids = [str(project["id"]) for _, project in group if project.get("id")]
        title = _problem_title(group[0][1]) or group[0][0].title or composite_id
        program_set: set[str] = set()
        for hub_project, _project in group:
            program_set.update(program_ids(hub_project_programs(hub_project)))
        summaries.append(
            {
                "id": composite_id,
                "title": title,
                "member_ids": member_ids,
                "programs": sorted(program_set),
                "auto": composite_id.startswith(AUTO_COMPOSITE_PREFIX),
            }
        )
    summaries.sort(key=lambda item: str(item.get("title") or ""))
    return summaries


def load_hub_composite(
    store: HubStore,
    composite_id: str,
    members: list[tuple[HubProject, dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    groups = _composite_groups(members)
    group = groups.get(composite_id)
    resolved_id = composite_id
    if group is None:
        for public_id, candidate in groups.items():
            for hub_project, project in candidate:
                if _explicit_composite_id(hub_project) == composite_id:
                    group = candidate
                    resolved_id = public_id
                    break
                problem = _problem_key(project)
                if problem and _auto_composite_id(problem) == composite_id:
                    group = candidate
                    resolved_id = public_id
                    break
            if group is not None:
                break
    if group is None:
        return None

    grouped: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for hub_project, project in group:
        pid = str(project.get("id") or hub_project.slug)
        if pid in seen:
            continue
        seen.add(pid)
        grouped.append((pid, project_from_client(project)))
    if len(grouped) < 2:
        return None
    composite = build_composite(resolved_id, grouped)
    if composite is None:
        return None
    return composite_to_client(composite)

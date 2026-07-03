"""Merge hypothesis trees from multiple projects sharing a ``composite_id``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from koi.adapters.paths import project_md
from koi.adapters.project_mount import list_mounts
from koi.adapters.repository import load_project
from koi.core.models import KanbanBoard, Node, Project
from koi.services.api_helpers import project_to_client


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    return meta, parts[2].lstrip("\n")


def read_composite_id(project_id: str) -> str | None:
    path = project_md(project_id)
    if not path.is_file():
        return None
    meta, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    raw = meta.get("composite_id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def list_composite_ids() -> list[str]:
    ids: set[str] = set()
    for mount in list_mounts():
        cid = read_composite_id(mount.project_id)
        if cid:
            ids.add(cid)
    return sorted(ids)


def members_for_composite(composite_id: str) -> list[str]:
    out: list[str] = []
    for mount in list_mounts():
        if read_composite_id(mount.project_id) == composite_id:
            out.append(mount.project_id)
    return sorted(out)


@dataclass
class NodeConflict:
    node_id: str
    field: str
    projects: dict[str, str]


@dataclass
class CompositeProject:
    composite_id: str
    title: str
    description: str
    members: list[dict[str, str]]
    project: Project
    conflicts: list[NodeConflict] = field(default_factory=list)


def _node_signature(node: Node) -> tuple[str, str, str | None, str]:
    return (
        node.node_type.value,
        node.title,
        node.parent_id,
        node.description.strip(),
    )


def _merge_nodes(
    member_projects: list[tuple[str, Project]],
) -> tuple[list[Node], list[NodeConflict]]:
    merged: dict[str, Node] = {}
    conflicts: list[NodeConflict] = []

    for project_id, project in member_projects:
        for node in project.nodes:
            existing = merged.get(node.id)
            if existing is None:
                merged[node.id] = node
                continue
            for field_name, getter in (
                ("title", lambda n: n.title),
                ("description", lambda n: n.description.strip()),
                ("parent_id", lambda n: n.parent_id or ""),
                ("node_type", lambda n: n.node_type.value),
            ):
                if getter(existing) != getter(node):
                    conflicts.append(
                        NodeConflict(
                            node_id=node.id,
                            field=field_name,
                            projects={
                                existing.project_id: str(getter(existing)),
                                project_id: str(getter(node)),
                            },
                        )
                    )
                    break

    return list(merged.values()), conflicts


def _merge_boards(member_projects: list[tuple[str, Project]]) -> list[KanbanBoard]:
    boards: list[KanbanBoard] = []
    seen: set[str] = set()
    for _project_id, project in member_projects:
        for board in project.boards:
            if board.id in seen:
                continue
            seen.add(board.id)
            boards.append(board)
    return boards


def _composite_title(member_projects: list[tuple[str, Project]]) -> str:
    problem_titles: list[str] = []
    for _pid, project in member_projects:
        for node in project.nodes:
            if node.node_type.value == "problem" and node.title.strip():
                problem_titles.append(node.title.strip())
                break
    if problem_titles and len(set(problem_titles)) == 1:
        return problem_titles[0]
    titles = [p.title for _, p in member_projects]
    if len(set(titles)) == 1:
        return titles[0]
    return member_projects[0][0].replace("-", " ").title()


def load_composite(composite_id: str) -> CompositeProject | None:
    member_ids = members_for_composite(composite_id)
    if len(member_ids) < 2:
        return None

    member_projects: list[tuple[str, Project]] = []
    for pid in member_ids:
        project = load_project(pid, sync_reports=False)
        if project is None:
            continue
        member_projects.append((pid, project))
    if len(member_projects) < 2:
        return None

    nodes, conflicts = _merge_nodes(member_projects)
    boards = _merge_boards(member_projects)

    titles = [p.title for _, p in member_projects]
    title = _composite_title(member_projects)
    descriptions = [p.description.strip() for _, p in member_projects if p.description.strip()]
    description = descriptions[0] if descriptions else ""

    merged = Project(
        id=f"composite:{composite_id}",
        title=title,
        description=description,
        literature_keywords=[],
        nodes=nodes,
        boards=boards,
    )

    members = [{"project_id": pid, "title": project.title} for pid, project in member_projects]

    return CompositeProject(
        composite_id=composite_id,
        title=title,
        description=description,
        members=members,
        project=merged,
        conflicts=conflicts,
    )


def composite_to_client(composite: CompositeProject) -> dict[str, Any]:
    payload = project_to_client(composite.project)
    payload["is_composite"] = True
    payload["composite_id"] = composite.composite_id
    payload["members"] = composite.members
    payload["conflicts"] = [
        {"node_id": c.node_id, "field": c.field, "projects": c.projects}
        for c in composite.conflicts
    ]
    for node in payload["nodes"]:
        node["source_project_id"] = node.get("project_id")
    for board in payload["boards"].values():
        owner_id = board.get("owner_node_id")
        owner = next((n for n in payload["nodes"] if n["id"] == owner_id), None)
        if owner:
            board["source_project_id"] = owner.get("project_id")
    return payload


def list_composites_summary() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for composite_id in list_composite_ids():
        member_ids = members_for_composite(composite_id)
        if len(member_ids) < 2:
            continue
        member_projects: list[tuple[str, Project]] = []
        programs: set[str] = set()
        for pid in member_ids:
            project = load_project(pid, sync_reports=False)
            if project:
                member_projects.append((pid, project))
            mount = next((m for m in list_mounts() if m.project_id == pid), None)
            if mount:
                programs.update(mount.programs)
        if len(member_projects) < 2:
            continue
        out.append(
            {
                "id": composite_id,
                "title": _composite_title(member_projects),
                "member_ids": member_ids,
                "programs": sorted(programs),
            }
        )
    return out

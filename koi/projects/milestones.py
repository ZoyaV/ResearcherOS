"""Use cases for method milestones (milestones.md under reports/<method>/)."""

from __future__ import annotations

from typing import Any

from koi.adapters import milestones as milestones_store
from koi.adapters import repository
from koi.core.models import Project


class EntityNotFoundError(LookupError):
    """Project or method node is missing."""


def _require_project(project_id: str) -> Project:
    project = repository.load_project(project_id, sync_reports=False)
    if project is None:
        raise EntityNotFoundError("Project not found")
    return project


def _enqueue_sync(project_id: str, reason: str, detail: str) -> None:
    try:
        from koi.adapters.project_sync_queue import enqueue_push

        enqueue_push(project_id, reason, detail)
    except Exception:
        pass


def _payload(
    exists: bool,
    milestones: list[milestones_store.Milestone],
    relative_path: str,
) -> dict[str, Any]:
    return {
        "exists": exists,
        "relative_path": f"reports/{relative_path}",
        "milestones": [milestones_store.milestone_to_dict(m) for m in milestones],
    }


def get_milestones(project_id: str, node_id: str) -> dict[str, Any]:
    project = _require_project(project_id)
    try:
        exists, milestones, rel = milestones_store.load_milestones(project, node_id)
    except milestones_store.MilestoneError as error:
        raise EntityNotFoundError(str(error)) from error
    return _payload(exists, milestones, rel)


def create_milestones(project_id: str, node_id: str) -> dict[str, Any]:
    project = _require_project(project_id)
    try:
        milestones, rel = milestones_store.create_milestones_file(project, node_id)
    except milestones_store.MilestoneError as error:
        raise EntityNotFoundError(str(error)) from error
    _enqueue_sync(project_id, "milestones", f"create {node_id}")
    return _payload(True, milestones, rel)


def save_milestones(
    project_id: str, node_id: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    project = _require_project(project_id)
    milestones = milestones_store.milestones_from_payload(items)
    try:
        # Ensure file exists (create if missing) then overwrite.
        path = milestones_store.milestones_path(project, node_id)
        saved, rel = milestones_store.save_milestones(project, node_id, milestones)
        _ = path
    except milestones_store.MilestoneError as error:
        raise EntityNotFoundError(str(error)) from error
    _enqueue_sync(project_id, "milestones", f"save {node_id}")
    return _payload(True, saved, rel)

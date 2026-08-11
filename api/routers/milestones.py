"""HTTP API for method milestones (reports/<method>/milestones.md)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_project
from koi.projects import milestones as milestone_commands

router = APIRouter(tags=["milestones"])


class SaveMilestonesBody(BaseModel):
    milestones: list[dict] = Field(default_factory=list)


@router.get("/projects/{project_id}/nodes/{node_id}/milestones")
def get_milestones(project_id: str, node_id: str) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        return milestone_commands.get_milestones(project_id, node_id)
    except milestone_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/projects/{project_id}/nodes/{node_id}/milestones")
def post_milestones(project_id: str, node_id: str) -> dict:
    """Create empty milestones.md for the method (idempotent if already present)."""
    get_project(project_id, sync_reports=False)
    try:
        return milestone_commands.create_milestones(project_id, node_id)
    except milestone_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/projects/{project_id}/nodes/{node_id}/milestones")
def put_milestones(project_id: str, node_id: str, body: SaveMilestonesBody) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        return milestone_commands.save_milestones(project_id, node_id, body.milestones)
    except milestone_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

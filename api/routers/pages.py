"""HTTP API for master HTML pages (koi-structure/pages)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.deps import get_project
from koi.projects import pages as page_commands

router = APIRouter(tags=["pages"])


class CreatePageBody(BaseModel):
    title: str = Field(default="Master report", min_length=1, max_length=200)


class AttachPageBody(BaseModel):
    page_id: str | None = None
    title: str | None = None
    visible: bool = False
    create: bool = False


class VisibilityBody(BaseModel):
    visible: bool


@router.get("/projects/{project_id}/pages")
def get_pages(project_id: str) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        return page_commands.list_pages(project_id)
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/projects/{project_id}/pages")
def post_page(project_id: str, body: CreatePageBody) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        return page_commands.create_page(project_id, body.title)
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/projects/{project_id}/pages/{page_id}")
def remove_page(project_id: str, page_id: str) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        page_commands.delete_page(project_id, page_id)
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"ok": True}


@router.get("/projects/{project_id}/pages/{page_id}/file/{file_path:path}")
def get_page_file(project_id: str, page_id: str, file_path: str = "index.html"):
    get_project(project_id, sync_reports=False)
    try:
        path = page_commands.page_file(project_id, page_id, file_path or "index.html")
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path)


@router.get("/projects/{project_id}/nodes/{node_id}/pages")
def get_node_pages(project_id: str, node_id: str) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        return {"attachments": page_commands.node_attachments(project_id, node_id)}
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/projects/{project_id}/nodes/{node_id}/pages")
def post_node_page(project_id: str, node_id: str, body: AttachPageBody) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        if body.create or not body.page_id:
            title = (body.title or "").strip() or "Master report"
            return page_commands.create_and_attach(
                project_id, node_id, title, visible=body.visible
            )
        attachments = page_commands.attach_existing(
            project_id, node_id, body.page_id, visible=body.visible
        )
        return {"attachments": attachments}
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/projects/{project_id}/nodes/{node_id}/pages/{page_id}")
def patch_node_page(
    project_id: str, node_id: str, page_id: str, body: VisibilityBody
) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        return {
            "attachments": page_commands.set_visible(
                project_id, node_id, page_id, body.visible
            )
        }
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/projects/{project_id}/nodes/{node_id}/pages/{page_id}")
def delete_node_page(project_id: str, node_id: str, page_id: str) -> dict:
    get_project(project_id, sync_reports=False)
    try:
        return {
            "attachments": page_commands.detach(project_id, node_id, page_id)
        }
    except page_commands.EntityNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

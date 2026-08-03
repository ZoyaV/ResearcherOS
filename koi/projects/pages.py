"""Use cases for master HTML pages attached to tree nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from koi.adapters import pages as pages_store
from koi.adapters import repository
from koi.core.models import Project


class EntityNotFoundError(LookupError):
    """Project, node, or page is missing."""


class PageConflictError(ValueError):
    """Invalid page request."""


def _require_project(project_id: str) -> Project:
    project = repository.load_project(project_id, sync_reports=False)
    if project is None:
        raise EntityNotFoundError("Project not found")
    return project


def _require_node(project: Project, node_id: str) -> None:
    if not any(node.id == node_id for node in project.nodes):
        raise EntityNotFoundError("Node not found")


def _enqueue_sync(project_id: str, reason: str, detail: str) -> None:
    try:
        from koi.adapters.project_sync_queue import enqueue_push

        enqueue_push(project_id, reason, detail)
    except Exception:
        pass


def list_pages(project_id: str) -> dict[str, Any]:
    _require_project(project_id)
    return {
        "pages": pages_store.list_pages(project_id),
        "pins": pages_store.visible_pins(project_id),
    }


def create_page(project_id: str, title: str) -> dict[str, Any]:
    _require_project(project_id)
    page = pages_store.create_page(project_id, title)
    _enqueue_sync(project_id, "pages", f"create {page['id']}")
    return page


def delete_page(project_id: str, page_id: str) -> None:
    _require_project(project_id)
    try:
        pages_store.delete_page(project_id, page_id)
    except pages_store.PageError as error:
        raise EntityNotFoundError(str(error)) from error
    _enqueue_sync(project_id, "pages", f"delete {page_id}")


def page_file(project_id: str, page_id: str, relative: str = "index.html") -> Path:
    _require_project(project_id)
    path = pages_store.resolve_page_file(project_id, page_id, relative)
    if path is None:
        raise EntityNotFoundError("Page file not found")
    return path


def node_attachments(project_id: str, node_id: str) -> list[dict[str, Any]]:
    project = _require_project(project_id)
    _require_node(project, node_id)
    return pages_store.attachments_for_node(project_id, node_id)


def attach_existing(
    project_id: str,
    node_id: str,
    page_id: str,
    *,
    visible: bool = False,
) -> list[dict[str, Any]]:
    project = _require_project(project_id)
    _require_node(project, node_id)
    try:
        items = pages_store.attach_page(
            project_id, node_id, page_id, visible=visible
        )
    except pages_store.PageError as error:
        raise EntityNotFoundError(str(error)) from error
    _enqueue_sync(project_id, "pages", f"attach {page_id} → {node_id}")
    return items


def create_and_attach(
    project_id: str,
    node_id: str,
    title: str,
    *,
    visible: bool = False,
) -> dict[str, Any]:
    project = _require_project(project_id)
    _require_node(project, node_id)
    page = pages_store.create_page(project_id, title)
    items = pages_store.attach_page(
        project_id, node_id, page["id"], visible=visible
    )
    _enqueue_sync(project_id, "pages", f"create+attach {page['id']} → {node_id}")
    return {"page": page, "attachments": items}


def detach(project_id: str, node_id: str, page_id: str) -> list[dict[str, Any]]:
    project = _require_project(project_id)
    _require_node(project, node_id)
    items = pages_store.detach_page(project_id, node_id, page_id)
    _enqueue_sync(project_id, "pages", f"detach {page_id} ← {node_id}")
    return items


def set_visible(
    project_id: str,
    node_id: str,
    page_id: str,
    visible: bool,
) -> list[dict[str, Any]]:
    project = _require_project(project_id)
    _require_node(project, node_id)
    try:
        items = pages_store.set_page_visible(
            project_id, node_id, page_id, visible
        )
    except pages_store.PageError as error:
        raise EntityNotFoundError(str(error)) from error
    _enqueue_sync(project_id, "pages", f"visible {page_id}@{node_id}={visible}")
    return items


def visible_pins(project_id: str) -> dict[str, list[dict[str, str]]]:
    try:
        _require_project(project_id)
    except EntityNotFoundError:
        return {}
    return pages_store.visible_pins(project_id)

"""Read-only KOI API routes so the main ResearchOS web UI works on Hub."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request

from hub.app.auth import get_session
from hub.app.config import HubConfig
from hub.app.access import can_view_project_with_store
from hub.app.hub_composite import list_hub_composites, load_hub_composite
from hub.app.project_identity import dedupe_hub_projects, project_rank
from hub.app.store import HubProject, HubStore
from koi.application.project_views import allowed_children
from koi.core.models import NodeType

router = APIRouter(tags=["koi-readonly"])


def _viewer_id(request: Request, config: HubConfig, store: HubStore) -> Optional[int]:
    session = get_session(request, config, store)
    return session.github_id if session else None


def _viewable_members(
    request: Request, config: HubConfig, store: HubStore
) -> list[tuple[HubProject, dict[str, Any]]]:
    viewer = _viewer_id(request, config, store)
    members: list[tuple[HubProject, dict[str, Any]]] = []
    for hub_project in dedupe_hub_projects(store.list_projects()):
        if not hub_project.enabled:
            continue
        if hub_project.visibility == "unlisted":
            continue
        if not can_view_project_with_store(hub_project, viewer, store):
            continue
        project = _snapshot_project(store, hub_project.slug)
        if project:
            members.append((hub_project, project))
    return members


def _viewable_projects(
    request: Request, config: HubConfig, store: HubStore
) -> list[HubProject]:
    return [hub_project for hub_project, _project in _viewable_members(request, config, store)]


def _snapshot_project(store: HubStore, slug: str) -> Optional[dict[str, Any]]:
    snap = store.get_snapshot(slug)
    if not snap:
        return None
    project = snap.get("project")
    return project if isinstance(project, dict) else None


def _find_slug_by_project_id(store: HubStore, project_id: str) -> Optional[str]:
    best_slug: Optional[str] = None
    best_rank: tuple[int, str, str] = (-1, "", "")
    for hub_project in store.list_projects():
        if not hub_project.enabled:
            continue
        project = _snapshot_project(store, hub_project.slug)
        if project and str(project.get("id") or "") == project_id:
            rank = project_rank(hub_project)
            if rank > best_rank:
                best_rank = rank
                best_slug = hub_project.slug
    return best_slug


def _project_summary(hub_project: HubProject, project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": project.get("id") or hub_project.slug,
        "title": project.get("title") or hub_project.title,
        "description": project.get("description") or "",
        "hub_slug": hub_project.slug,
        "owner_login": hub_project.owner_login,
    }


@router.get("/health")
def koi_health() -> dict[str, str]:
    return {"status": "ok", "storage": "hub-snapshot"}


@router.get("/meta/node-types")
def node_types_meta() -> dict[str, Any]:
    return {
        "types": [t.value for t in NodeType],
        "labels": {
            NodeType.PROBLEM.value: "Проблема",
            NodeType.CAUSE.value: "Причина",
            NodeType.CAUSE_EVIDENCE.value: "Доказательство причины",
            NodeType.REMEDIATION.value: "Гипотеза устранения",
            NodeType.METHOD.value: "Метод",
            NodeType.EXPERIMENT.value: "Эксперимент",
        },
        "kanban_owners": ["method"],
        "allowed_children": {
            "problem": allowed_children("problem"),
            "cause": allowed_children("cause"),
            "cause_evidence": allowed_children("cause_evidence"),
            "remediation": allowed_children("remediation"),
            "method": allowed_children("method"),
            "experiment": allowed_children("experiment"),
            None: allowed_children(None),
        },
    }


@router.get("/laboratory")
def get_laboratory() -> dict[str, str]:
    return {
        "id": "researchos-hub",
        "title": "ResearchOS Hub",
        "description": "Публичные и сетевые исследовательские проекты",
    }


@router.get("/projects")
def list_projects(request: Request) -> list[dict[str, Any]]:
    config: HubConfig = request.app.state.hub_config
    store: HubStore = request.app.state.hub_store
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for hub_project in _viewable_projects(request, config, store):
        project = _snapshot_project(store, hub_project.slug)
        if not project:
            continue
        pid = str(project.get("id") or hub_project.slug)
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        items.append(_project_summary(hub_project, project))
    items.sort(key=lambda x: str(x.get("title") or ""))
    return items


@router.get("/projects/grouped")
def projects_grouped(request: Request) -> dict[str, Any]:
    config: HubConfig = request.app.state.hub_config
    store: HubStore = request.app.state.hub_store
    members = _viewable_members(request, config, store)
    composites = list_hub_composites(members)
    hidden_member_ids: set[str] = set()
    for composite in composites:
        hidden_member_ids.update(composite.get("member_ids") or [])

    projects: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for hub_project, project in members:
        pid = str(project.get("id") or hub_project.slug)
        if pid in hidden_member_ids or pid in seen_ids:
            continue
        seen_ids.add(pid)
        summary = _project_summary(hub_project, project)
        if hub_project.composite_id:
            summary["composite_id"] = hub_project.composite_id
        projects.append(summary)
    projects.sort(key=lambda x: str(x.get("title") or ""))

    lab = get_laboratory()
    if composites:
        return {
            "laboratory": lab,
            "composites": composites,
            "groups": [
                {
                    "id": "",
                    "title": "Проекты",
                    "description": "",
                    "composites": composites,
                    "projects": projects,
                }
            ],
            "ungrouped": [],
        }
    return {
        "laboratory": lab,
        "composites": [],
        "groups": [],
        "ungrouped": projects,
    }


@router.get("/composites")
def list_composites(request: Request) -> list[dict[str, Any]]:
    config: HubConfig = request.app.state.hub_config
    store: HubStore = request.app.state.hub_store
    return list_hub_composites(_viewable_members(request, config, store))


@router.get("/composites/{composite_id}")
def get_composite(request: Request, composite_id: str) -> dict[str, Any]:
    config: HubConfig = request.app.state.hub_config
    store: HubStore = request.app.state.hub_store
    members = _viewable_members(request, config, store)
    payload = load_hub_composite(store, composite_id, members)
    if payload is None:
        raise HTTPException(404, "Composite not found or fewer than two members")
    return payload


@router.get("/projects/{project_id}")
def get_project(request: Request, project_id: str) -> dict[str, Any]:
    config: HubConfig = request.app.state.hub_config
    store: HubStore = request.app.state.hub_store

    slug = project_id
    hub_project = store.get_project(slug)
    if hub_project is None:
        slug = _find_slug_by_project_id(store, project_id) or ""
        hub_project = store.get_project(slug) if slug else None

    if hub_project is None:
        raise HTTPException(404, "Project not found")

    viewer = _viewer_id(request, config, store)
    if not can_view_project_with_store(hub_project, viewer, store):
        raise HTTPException(403, "Not allowed to view this project")

    project = _snapshot_project(store, hub_project.slug)
    if project is None:
        raise HTTPException(404, "Snapshot missing")
    return project


@router.get("/projects/{project_id}/kanban/running-activity")
def kanban_running_activity(_request: Request, project_id: str) -> dict[str, Any]:
    return {"project_id": project_id, "cards": []}


@router.get("/projects/{project_id}/kanban/live-monitor")
def kanban_live_monitor(_request: Request, project_id: str) -> dict[str, Any]:
    return {"project_id": project_id, "boards": {}}


@router.get("/projects/{project_id}/boards/{board_id}/dag-layout")
def get_board_dag_layout(request: Request, project_id: str, board_id: str) -> dict[str, Any]:
    config: HubConfig = request.app.state.hub_config
    store: HubStore = request.app.state.hub_store

    slug = project_id
    hub_project = store.get_project(slug)
    if hub_project is None:
        slug = _find_slug_by_project_id(store, project_id) or ""
        hub_project = store.get_project(slug) if slug else None
    if hub_project is None:
        raise HTTPException(404, "Project not found")

    viewer = _viewer_id(request, config, store)
    if not can_view_project_with_store(hub_project, viewer, store):
        raise HTTPException(403, "Not allowed to view this project")

    snap = store.get_snapshot(hub_project.slug)
    if not snap:
        raise HTTPException(404, "Snapshot missing")
    layouts = snap.get("dag_layouts") or {}
    if isinstance(layouts, dict) and board_id in layouts:
        layout = layouts[board_id]
        if isinstance(layout, dict):
            return layout
    return {
        "version": 1,
        "board_id": board_id,
        "updated_at": None,
        "cards": {},
    }


@router.get("/projects/{project_id}/boards/{board_id}/cards/{card_id}/report")
def card_report_stub(
    request: Request, project_id: str, board_id: str, card_id: str
) -> dict[str, Any]:
    project = get_project(request, project_id)
    boards = project.get("boards") or {}
    board = boards.get(board_id) or {}
    card = next((c for c in board.get("cards") or [] if c.get("id") == card_id), None)
    if not card:
        raise HTTPException(404, "Card not found")
    desc = str(card.get("description") or "").strip()
    content = desc or f"_Отчёт недоступен в Hub (только снимок канбана). Карточка: {card.get('title', card_id)}._"
    return {"content": content, "path": None, "readonly": True}


@router.get("/projects/{project_id}/boards/{board_id}/cards/{card_id}/report-path")
def card_report_path_stub(
    request: Request, project_id: str, board_id: str, card_id: str
) -> dict[str, Any]:
    card_report_stub(request, project_id, board_id, card_id)
    return {"path": None, "readonly": True}


@router.get("/settings")
def settings_stub() -> dict[str, Any]:
    return {
        "agent_chat_mode": "cursor_inbox",
        "cursor_api_key_configured": False,
        "inbox_configured": False,
        "hub_readonly": True,
    }


@router.get("/sync/status")
def sync_status_stub() -> dict[str, Any]:
    return {"ok": True, "behind": 0, "hub_readonly": True}


@router.get("/sync/project-discovery")
def project_discovery_stub(since: int = 0) -> dict[str, Any]:
    return {"ok": True, "revision": since, "changes": {"added": [], "removed": [], "changed": []}}


@router.get("/sync/rq-discoveries/feed")
def rq_feed_stub(limit: int = 50) -> dict[str, Any]:
    return {"items": [], "limit": limit}


@router.get("/sync/rq-discoveries")
def rq_discoveries_stub() -> dict[str, Any]:
    return {"pending": [], "items": []}


@router.get("/agent-chat")
def agent_chat_stub(project_id: str = "") -> dict[str, Any]:
    return {"items": [], "project_id": project_id}


@router.get("/cursor/usage")
def cursor_usage_stub() -> dict[str, Any]:
    return {"available": False, "hub_readonly": True}

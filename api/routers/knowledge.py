from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from api.deps import get_project
from koi.services.knowledge import (
    knowledge_log_path,
    knowledge_summary,
    render_project_knowledge,
    write_project_knowledge,
)
from koi.adapters.repository import load_project
from koi.adapters.paths import koi_root, repo_root

router = APIRouter(tags=["knowledge"])


def _resolve_project_markdown_path(project_id: str, path: str) -> Path:
    """Markdown under ``koi-structure/`` or repo ``docs/*.md``."""
    raw = path.strip().lstrip("/")
    if not raw or ".." in Path(raw).parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    koi = koi_root(project_id).resolve()
    repo = repo_root(project_id).resolve()
    koi_prefix = str(koi) + "/"
    repo_prefix = str(repo) + "/"

    target = (koi / raw).resolve()
    if (str(target).startswith(koi_prefix) or target == koi) and target.suffix == ".md":
        if target.is_file():
            return target

    if raw.startswith("docs/"):
        doc_target = (repo / raw).resolve()
        if (
            str(doc_target).startswith(repo_prefix)
            and doc_target.suffix == ".md"
            and doc_target.is_file()
        ):
            return doc_target

    raise HTTPException(status_code=404, detail=f"Файл не найден: {path}")


def _resolve_project_asset_path(project_id: str, path: str) -> Path:
    raw = path.strip().lstrip("/")
    if not raw or ".." in Path(raw).parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    koi = koi_root(project_id).resolve()
    repo = repo_root(project_id).resolve()
    koi_prefix = str(koi) + "/"
    repo_prefix = str(repo) + "/"

    target = (koi / raw).resolve()
    if (str(target).startswith(koi_prefix) or target == koi) and target.is_file():
        return target

    if raw.startswith("docs/"):
        doc_target = (repo / raw).resolve()
        if str(doc_target).startswith(repo_prefix) and doc_target.is_file():
            return doc_target

    raise HTTPException(status_code=404, detail=f"Файл не найден: {path}")


@router.get("/projects/{project_id}/knowledge")
def get_project_knowledge(project_id: str):
    project = get_project(project_id, sync_reports=False)
    try:
        write_project_knowledge(project)
    except Exception:  # noqa: BLE001
        pass
    return PlainTextResponse(
        render_project_knowledge(project),
        media_type="text/markdown; charset=utf-8",
    )


@router.get("/projects/{project_id}/knowledge/summary")
def get_project_knowledge_summary(project_id: str):
    project = load_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        write_project_knowledge(project)
    except Exception:  # noqa: BLE001
        pass
    return knowledge_summary(project)


@router.get("/projects/{project_id}/knowledge/log")
def get_project_knowledge_log(project_id: str):
    get_project(project_id, sync_reports=False)
    path = knowledge_log_path(project_id)
    text = path.read_text(encoding="utf-8") if path.exists() else (
        "# Журнал базы знаний\n\n_Записей пока нет — журнал наполняется автоматически "
        "при сохранении проекта (вердикты, инсайты, новые документы)._\n"
    )
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")


@router.get("/projects/{project_id}/knowledge/file")
def get_project_knowledge_file(project_id: str, path: str):
    get_project(project_id, sync_reports=False)
    target = _resolve_project_markdown_path(project_id, path)
    return PlainTextResponse(
        target.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8"
    )


@router.get("/projects/{project_id}/knowledge/asset")
def get_project_knowledge_asset(project_id: str, path: str) -> FileResponse:
    get_project(project_id, sync_reports=False)
    target = _resolve_project_asset_path(project_id, path)
    return FileResponse(target)

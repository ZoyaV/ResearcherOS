from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from pathlib import Path

from api.deps import parse_project
from koi.services.paper_catalog import (
    DEFAULT_PAPER_SLUG,
    get_paper_slot_dir,
    list_project_papers,
    normalize_paper_slug,
    find_pdf,
)
from koi.adapters.settings_store import is_cursor_inbox_agent_mode
from koi.services.paper_generator import (
    PDF_NAME,
    TEX_NAME,
    generate_paper,
    paper_status,
)
from koi.services.paper_runner import submit_paper_request

router = APIRouter(tags=["paper"])


class PaperGenerateBody(BaseModel):
    slug: str = Field(default=DEFAULT_PAPER_SLUG)


def _resolve_slot(project_id: str, slug: str | None) -> tuple[str, Path | None]:
    papers = list_project_papers(project_id)
    if slug is None:
        if not papers:
            return DEFAULT_PAPER_SLUG, None
        preferred = next((item for item in papers if item["slug"] == DEFAULT_PAPER_SLUG), papers[0])
        slug = preferred["slug"]
    try:
        normalized = normalize_paper_slug(slug)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    slot_dir = get_paper_slot_dir(project_id, normalized)
    return normalized, slot_dir


@router.get("/projects/{project_id}/papers")
def get_project_papers(project_id: str) -> dict:
    parse_project(project_id)
    papers = list_project_papers(project_id)
    return {"papers": papers, "default_slug": DEFAULT_PAPER_SLUG}


@router.post("/projects/{project_id}/paper")
def post_project_paper(
    project_id: str,
    background_tasks: BackgroundTasks,
    slug: str | None = Query(default=None),
    body: PaperGenerateBody | None = None,
) -> dict:
    """Сгенерировать (или перегенерировать) статью NeurIPS по графу исследования."""
    parse_project(project_id)
    paper_slug = normalize_paper_slug((body.slug if body else None) or slug)
    try:
        result = submit_paper_request(project_id, paper_slug=paper_slug)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

    if result.get("mode") == "background":
        background_tasks.add_task(generate_paper, project_id, paper_slug)

    return {
        "ok": True,
        "slug": paper_slug,
        "mode": result.get("mode"),
        "status": result.get("paper_status") or paper_status(project_id, paper_slug),
        "item_id": result.get("item_id"),
        "inbox_message": result.get("inbox_message") if is_cursor_inbox_agent_mode() else None,
    }


@router.get("/projects/{project_id}/paper/status")
def get_project_paper_status_legacy(
    project_id: str,
    slug: str | None = Query(default=None),
) -> dict:
    parse_project(project_id)
    return paper_status(project_id, normalize_paper_slug(slug))


@router.get("/projects/{project_id}/papers/{slug}/status")
def get_project_paper_status(project_id: str, slug: str) -> dict:
    parse_project(project_id)
    normalized = normalize_paper_slug(slug)
    return paper_status(project_id, normalized)


@router.get("/projects/{project_id}/paper/pdf")
def get_project_paper_pdf_legacy(
    project_id: str,
    slug: str | None = Query(default=None),
) -> FileResponse:
    parse_project(project_id)
    normalized, slot_dir = _resolve_slot(project_id, slug)
    if slot_dir is None:
        raise HTTPException(404, "PDF статьи ещё не сгенерирован")
    path = find_pdf(slot_dir)
    if path is None or not path.is_file():
        raise HTTPException(404, "PDF статьи ещё не сгенерирован")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.get("/projects/{project_id}/papers/{slug}/pdf")
def get_project_paper_pdf(project_id: str, slug: str) -> FileResponse:
    parse_project(project_id)
    normalized = normalize_paper_slug(slug)
    slot_dir = get_paper_slot_dir(project_id, normalized)
    if slot_dir is None:
        raise HTTPException(404, f"Статья «{normalized}» не найдена")
    path = find_pdf(slot_dir)
    if path is None or not path.is_file():
        raise HTTPException(404, "PDF статьи ещё не сгенерирован")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.get("/projects/{project_id}/paper/tex")
def get_project_paper_tex_legacy(
    project_id: str,
    slug: str | None = Query(default=None),
):
    parse_project(project_id)
    normalized, slot_dir = _resolve_slot(project_id, slug)
    if slot_dir is None:
        raise HTTPException(404, "main.tex ещё не сгенерирован")
    path = slot_dir / TEX_NAME
    if not path.is_file():
        raise HTTPException(404, "main.tex ещё не сгенерирован")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8"
    )


@router.get("/projects/{project_id}/papers/{slug}/tex")
def get_project_paper_tex(project_id: str, slug: str):
    parse_project(project_id)
    normalized = normalize_paper_slug(slug)
    slot_dir = get_paper_slot_dir(project_id, normalized)
    if slot_dir is None:
        raise HTTPException(404, f"Статья «{normalized}» не найдена")
    path = slot_dir / TEX_NAME
    if not path.is_file():
        raise HTTPException(404, "main.tex ещё не сгенерирован")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8"
    )

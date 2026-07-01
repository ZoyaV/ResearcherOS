from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from api.deps import parse_project
from koi.adapters.paths import paper_dir
from koi.adapters.settings_store import is_cursor_inbox_agent_mode
from koi.services.paper_generator import generate_paper, paper_status
from koi.services.paper_runner import submit_paper_request

router = APIRouter(tags=["paper"])


@router.post("/projects/{project_id}/paper")
def post_project_paper(project_id: str, background_tasks: BackgroundTasks) -> dict:
    """Сгенерировать (или перегенерировать) статью NeurIPS по графу исследования."""
    parse_project(project_id)
    try:
        result = submit_paper_request(project_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

    if result.get("mode") == "background":
        background_tasks.add_task(generate_paper, project_id)

    return {
        "ok": True,
        "mode": result.get("mode"),
        "status": result.get("paper_status") or paper_status(project_id),
        "item_id": result.get("item_id"),
        "inbox_message": result.get("inbox_message") if is_cursor_inbox_agent_mode() else None,
    }


@router.get("/projects/{project_id}/paper/status")
def get_project_paper_status(project_id: str) -> dict:
    parse_project(project_id)
    return paper_status(project_id)


@router.get("/projects/{project_id}/paper/pdf")
def get_project_paper_pdf(project_id: str) -> FileResponse:
    parse_project(project_id)
    path = paper_dir(project_id) / "paper.pdf"
    if not path.is_file():
        raise HTTPException(404, "PDF статьи ещё не сгенерирован")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="paper.pdf"'},
    )


@router.get("/projects/{project_id}/paper/tex")
def get_project_paper_tex(project_id: str):
    parse_project(project_id)
    path = paper_dir(project_id) / "main.tex"
    if not path.is_file():
        raise HTTPException(404, "main.tex ещё не сгенерирован")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8"
    )

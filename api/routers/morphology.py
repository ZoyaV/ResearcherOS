from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import parse_project
from api.schemas import MorphologyStageBody
from koi.literature.morphology import (
    build_morphology_article,
    delete_morphology_run,
    list_morphology_runs,
    load_morphology_run,
    stage_paper_morphology,
)
from koi.literature.morphology_presentation import (
    delete_presentation_run,
    list_presentation_runs,
    load_presentation_run,
    stage_morphology_presentation,
)

router = APIRouter(tags=["morphology"])


@router.post("/projects/{project_id}/morphology/stage")
def post_project_morphology_stage(
    project_id: str,
    body: MorphologyStageBody,
) -> dict[str, object]:
    """Stage one paper; return a Cursor chat prompt (no LLM API)."""
    parse_project(project_id)
    try:
        return stage_paper_morphology(project_id, body.paper)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/projects/{project_id}/morphology")
def get_project_morphology_history(
    project_id: str,
    paper_key: str = "",
) -> dict[str, object]:
    parse_project(project_id)
    runs = list_morphology_runs(project_id, paper_key_filter=paper_key)
    return {"count": len(runs), "runs": runs}


@router.get("/projects/{project_id}/morphology/{run_id}")
def get_project_morphology_run(project_id: str, run_id: str) -> dict[str, object]:
    parse_project(project_id)
    payload = load_morphology_run(project_id, run_id)
    if payload is None:
        raise HTTPException(404, f"Morphology run '{run_id}' was not found.")
    return payload


@router.get("/projects/{project_id}/morphology/{run_id}/article")
def get_project_morphology_article(project_id: str, run_id: str) -> dict[str, object]:
    """Return the paper text/HTML with graph evidence quotes marked up."""
    parse_project(project_id)
    payload = build_morphology_article(project_id, run_id)
    if payload is None:
        raise HTTPException(404, f"Morphology run '{run_id}' was not found.")
    return payload


@router.post("/projects/{project_id}/morphology/{run_id}/presentations/stage")
def post_project_morphology_presentation_stage(
    project_id: str,
    run_id: str,
) -> dict[str, object]:
    """Stage a presentation from a completed morphology graph."""
    parse_project(project_id)
    try:
        return stage_morphology_presentation(project_id, run_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/projects/{project_id}/morphology/{run_id}/presentations")
def get_project_morphology_presentations(
    project_id: str,
    run_id: str,
) -> dict[str, object]:
    parse_project(project_id)
    runs = list_presentation_runs(project_id, run_id)
    return {"count": len(runs), "runs": runs}


@router.get("/projects/{project_id}/morphology/{run_id}/presentations/{presentation_id}")
def get_project_morphology_presentation(
    project_id: str,
    run_id: str,
    presentation_id: str,
) -> dict[str, object]:
    parse_project(project_id)
    payload = load_presentation_run(project_id, run_id, presentation_id)
    if payload is None:
        raise HTTPException(404, f"Presentation run '{presentation_id}' was not found.")
    return payload


@router.delete("/projects/{project_id}/morphology/{run_id}/presentations/{presentation_id}")
def delete_project_morphology_presentation(
    project_id: str,
    run_id: str,
    presentation_id: str,
) -> dict[str, object]:
    parse_project(project_id)
    try:
        return delete_presentation_run(project_id, run_id, presentation_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/projects/{project_id}/morphology/{run_id}")
def delete_project_morphology_run(project_id: str, run_id: str) -> dict[str, object]:
    parse_project(project_id)
    try:
        return delete_morphology_run(project_id, run_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

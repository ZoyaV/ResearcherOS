from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import CreateProgramBody
from koi.services.programs import (
    create_program,
    grouped_projects,
    list_programs,
    load_laboratory,
    program_summary,
)

router = APIRouter(tags=["programs"])


@router.get("/laboratory")
def get_laboratory() -> dict:
    return load_laboratory()


@router.get("/programs")
def get_programs() -> list[dict]:
    return list_programs()


@router.get("/programs/{program_id}")
def get_program(program_id: str) -> dict:
    summary = program_summary(program_id)
    if summary is None:
        raise HTTPException(404, "Program not found")
    return summary


@router.post("/programs")
def post_program(body: CreateProgramBody) -> dict:
    return create_program(body.title, body.description)


@router.get("/projects/grouped")
def projects_grouped() -> dict:
    return grouped_projects()

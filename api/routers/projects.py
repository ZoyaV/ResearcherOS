from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.deps import enqueue_sync, find_card, get_project as require_project, parse_project
from api.schemas import (
    CardReportBody,
    CreateCardBody,
    CreateNodeBody,
    CreateProjectBody,
    DagSuggestBody,
    DagLayoutBody,
    UpdateCardBody,
    UpdateNodeBody,
)
from koi.application import project_commands
from koi.application.project_views import project_to_client
from koi.adapters.card_reports import (
    read_report,
    read_report_indexed,
    report_path_info,
    resolve_report_asset_path,
    save_report_asset,
    write_report,
)
from koi.adapters.repository import list_projects
from koi.services import dag_layout
from koi.services.card_live import (
    live_monitor_cards,
    live_snapshot,
    merge_live_hints,
    resolve_project_path,
)
from koi.services.rq_discoveries import running_kanban_activity

router = APIRouter(tags=["projects"])


@router.get("/projects")
def projects() -> list[dict]:
    return list_projects(with_programs=True)


@router.post("/projects")
def post_project(body: CreateProjectBody) -> dict:
    try:
        project = project_commands.create_project(
            project_commands.CreateProjectCommand(
                title=body.title,
                project_id=body.tag,
                description=body.description,
                program_id=body.program_id,
                program_title=body.program_title,
            )
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return project_to_client(project)


@router.get("/projects/{project_id}")
def read_project(project_id: str) -> dict:
    return project_to_client(require_project(project_id, sync_reports=False))


@router.get("/projects/{project_id}/kanban/running-activity")
def get_kanban_running_activity(project_id: str) -> dict:
    require_project(project_id, sync_reports=False)
    return {"ok": True, "items": running_kanban_activity(project_id)}


@router.get("/projects/{project_id}/kanban/live-monitor")
def get_kanban_live_monitor(project_id: str) -> dict:
    project = require_project(project_id, sync_reports=False)
    return {"ok": True, "items": live_monitor_cards(project_id, project)}


@router.put("/projects/{project_id}")
def put_project(project_id: str, payload: dict) -> dict:
    try:
        project = project_commands.replace_project(project_id, payload)
    except project_commands.EntityNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return project_to_client(project)


@router.post("/projects/{project_id}/nodes")
def post_node(project_id: str, body: CreateNodeBody) -> dict:
    try:
        project = project_commands.create_node(
            project_id,
            project_commands.CreateNodeCommand(
                parent_id=body.parent_id,
                node_type=body.node_type,
                title=body.title,
                description=body.description,
            ),
        )
    except project_commands.EntityNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return project_to_client(project)


@router.patch("/projects/{project_id}/nodes/{node_id}")
def patch_node(project_id: str, node_id: str, body: UpdateNodeBody) -> dict:
    research_questions = None
    if body.research_questions is not None:
        research_questions = [
            project_commands.ResearchQuestionInput(
                id=item.id,
                question=item.question,
                answer=item.answer,
                narrative=item.narrative,
                certainty=item.certainty,
                importance=item.importance,
                card_id=item.card_id,
            )
            for item in body.research_questions
        ]
    try:
        project = project_commands.update_node(
            project_id,
            node_id,
            project_commands.UpdateNodeCommand(
                title=body.title,
                description=body.description,
                research_questions=research_questions,
            ),
        )
    except project_commands.EntityNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return project_to_client(project)


@router.delete("/projects/{project_id}/nodes/{node_id}")
def remove_node(project_id: str, node_id: str) -> dict:
    try:
        project = project_commands.delete_node(project_id, node_id)
    except project_commands.EntityNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return project_to_client(project)


@router.post("/projects/{project_id}/boards/{board_id}/cards")
def post_card(project_id: str, board_id: str, body: CreateCardBody) -> dict:
    try:
        project = project_commands.create_card(
            project_id,
            board_id,
            project_commands.CreateCardCommand(
                column_id=body.column_id,
                title=body.title,
                description=body.description,
                tags=tuple(body.tags),
                depends_on=tuple(body.depends_on),
            ),
        )
    except project_commands.EntityNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return project_to_client(project)


@router.patch("/projects/{project_id}/boards/{board_id}/cards/{card_id}")
def patch_card(
    project_id: str, board_id: str, card_id: str, body: UpdateCardBody
) -> dict:
    try:
        project = project_commands.update_card(
            project_id,
            board_id,
            card_id,
            project_commands.UpdateCardCommand(
                title=body.title,
                description=body.description,
                column_id=body.column_id,
                tags=tuple(body.tags) if body.tags is not None else None,
                depends_on=tuple(body.depends_on) if body.depends_on is not None else None,
            ),
        )
    except project_commands.EntityNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return project_to_client(project)


@router.post("/projects/{project_id}/boards/{board_id}/dag/suggest")
def post_board_dag_suggest(
    project_id: str, board_id: str, body: DagSuggestBody
) -> dict:
    try:
        result = project_commands.suggest_board_dependencies(
            project_id,
            board_id,
            apply=body.apply,
        )
    except project_commands.EntityNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    if result.applied is not None:
        return {
            "suggestions": result.suggestions,
            "applied": result.applied,
            "project": project_to_client(result.project),
        }
    return {"suggestions": result.suggestions}


@router.get("/projects/{project_id}/boards/{board_id}/dag-layout")
def get_board_dag_layout(project_id: str, board_id: str) -> dict:
    project = parse_project(project_id)
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    return dag_layout.load_dag_layout(project_id, board_id)


@router.put("/projects/{project_id}/boards/{board_id}/dag-layout")
def put_board_dag_layout(
    project_id: str, board_id: str, body: DagLayoutBody
) -> dict:
    project = require_project(project_id)
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    valid_ids = {c.id for c in board.cards}
    return dag_layout.save_dag_layout(
        project_id,
        board_id,
        body.cards,
        valid_card_ids=valid_ids,
    )


@router.delete("/projects/{project_id}/boards/{board_id}/cards/{card_id}")
def delete_card(project_id: str, board_id: str, card_id: str) -> dict:
    try:
        project = project_commands.delete_card(project_id, board_id, card_id)
    except project_commands.EntityNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return project_to_client(project)


@router.get("/projects/{project_id}/boards/{board_id}/cards/{card_id}/report")
def get_card_report(project_id: str, board_id: str, card_id: str) -> dict:
    project = parse_project(project_id)
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    card = next((c for c in board.cards if c.id == card_id), None)
    if card is not None:
        return read_report(project, board_id, card_id, card.title)
    indexed = read_report_indexed(project_id, card_id)
    if indexed is not None:
        return indexed
    raise HTTPException(404, "Card not found")


@router.get("/projects/{project_id}/boards/{board_id}/cards/{card_id}/report-path")
def get_card_report_path(project_id: str, board_id: str, card_id: str) -> dict:
    project = parse_project(project_id)
    _, card = find_card(project, board_id, card_id)
    return report_path_info(project, board_id, card_id, card.title)


@router.put("/projects/{project_id}/boards/{board_id}/cards/{card_id}/report")
def put_card_report(
    project_id: str, board_id: str, card_id: str, body: CardReportBody
) -> dict:
    project = parse_project(project_id)
    _, card = find_card(project, board_id, card_id)
    result = write_report(project, board_id, card_id, card.title, body.content)
    enqueue_sync(project_id, "report_saved", f"отчёт карточки {card.title}")
    return result


@router.post("/projects/{project_id}/boards/{board_id}/cards/{card_id}/report/assets")
async def post_report_asset(
    project_id: str,
    board_id: str,
    card_id: str,
    file: UploadFile = File(...),
) -> dict:
    project = parse_project(project_id)
    _, card = find_card(project, board_id, card_id)
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    try:
        return save_report_asset(
            project,
            board_id,
            card_id,
            card.title,
            data,
            file.content_type or "application/octet-stream",
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/projects/{project_id}/boards/{board_id}/cards/{card_id}/live")
def get_card_live(
    project_id: str,
    board_id: str,
    card_id: str,
    tail_lines: int = 100,
) -> dict:
    project = parse_project(project_id)
    _, card = find_card(project, board_id, card_id)
    hints = merge_live_hints(project, board_id, card_id, card.title, card.description)
    snapshot = live_snapshot(
        project_id,
        hints=hints,
        description=card.description,
        tail_lines=tail_lines,
        column_id=card.column_id,
    )
    return {
        "ok": True,
        "card_id": card_id,
        "column_id": card.column_id,
        "title": card.title,
        **snapshot,
    }


@router.get("/projects/{project_id}/live/file")
def get_live_file(project_id: str, path: str) -> FileResponse:
    require_project(project_id, sync_reports=False)
    try:
        resolved = resolve_project_path(project_id, path)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not resolved.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(resolved)


@router.get("/projects/{project_id}/boards/{board_id}/cards/{card_id}/report/assets/{asset_name}")
def get_report_asset(
    project_id: str,
    board_id: str,
    card_id: str,
    asset_name: str,
) -> FileResponse:
    project = parse_project(project_id)
    _, card = find_card(project, board_id, card_id)
    try:
        path = resolve_report_asset_path(
            project, board_id, card_id, card.title, asset_name
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, "Asset not found") from e
    return FileResponse(path)

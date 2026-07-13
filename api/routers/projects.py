from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.deps import enqueue_sync, find_card, get_project as require_project, parse_project
from api.schemas import (
    CardReportBody,
    CreateCardBody,
    CreateNodeBody,
    CreateProjectBody,
    DagSuggestBody,
    UpdateCardBody,
    UpdateNodeBody,
)
from koi.services.api_helpers import project_to_client
from koi.adapters.card_reports import (
    delete_report,
    ensure_card_report,
    read_report,
    read_report_indexed,
    rename_report_for_card,
    report_path_info,
    resolve_report_asset_path,
    save_report_asset,
    write_report,
)
from koi.core.md_io import normalize_card_tags, register_project_card_tags
from koi.core.models import (
    DEFAULT_KANBAN_COLUMNS,
    ExperimentCard,
    KanbanBoard,
    KanbanColumn,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
    Verdict,
)
from koi.adapters.repository import (
    add_node,
    create_project,
    delete_node,
    list_projects,
    save_project,
    update_board,
    update_node,
)
from koi.services.card_live import (
    live_monitor_cards,
    live_snapshot,
    merge_live_hints,
    resolve_project_path,
)
from koi.services.dag_suggest import (
    _normalize_dep_ids,
    _would_create_cycle,
    apply_dag_suggestions,
    suggest_board_dag,
)
from koi.services.rq_discoveries import running_kanban_activity

router = APIRouter(tags=["projects"])


@router.get("/projects")
def projects() -> list[dict]:
    return list_projects(with_programs=True)


@router.post("/projects")
def post_project(body: CreateProjectBody) -> dict:
    if body.program_id and body.program_title:
        raise HTTPException(400, "Specify either program_id or program_title, not both")

    programs: list[str] = []
    if body.program_id:
        programs.append(body.program_id.strip())
    elif body.program_title:
        from koi.services.programs import _slugify as slug_program

        programs.append(slug_program(body.program_title))

    try:
        project = create_project(
            body.title,
            project_id=body.tag,
            description=body.description,
            programs=programs,
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
    existing = require_project(project_id)
    project = Project(
        id=project_id,
        title=payload.get("title", existing.title),
        description=payload.get("description", existing.description),
    )
    nodes = []
    for raw in payload.get("nodes", []):
        rq_raw = raw.get("research_questions") or []
        research_questions = [
            MethodResearchQuestion(
                id=item.get("id") or f"rq-{uuid4().hex[:8]}",
                question=item["question"],
                answer=item.get("answer", ""),
                narrative=item.get("narrative", ""),
                certainty=ResearchQuestionCertainty(
                    item.get("certainty", ResearchQuestionCertainty.DEFINITE.value)
                ),
                importance=max(1, min(5, int(item.get("importance", 3)))),
                card_id=item.get("card_id"),
            )
            for item in rq_raw
        ]
        nodes.append(
            Node(
                id=raw["id"],
                project_id=project_id,
                parent_id=raw.get("parent_id"),
                node_type=NodeType(raw["node_type"]),
                title=raw["title"],
                description=raw.get("description", ""),
                verdict=Verdict(raw.get("verdict", "open")),
                research_questions=research_questions,
            )
        )
    boards = []
    for bid, raw in payload.get("boards", {}).items():
        cols = [
            KanbanColumn(**c) if isinstance(c, dict) else c
            for c in raw.get("columns", DEFAULT_KANBAN_COLUMNS)
        ]
        cards = [ExperimentCard(**c) for c in raw.get("cards", [])]
        boards.append(
            KanbanBoard(
                id=raw.get("id", bid),
                owner_node_id=raw["owner_node_id"],
                columns=cols,
                cards=cards,
            )
        )
    project.nodes = nodes
    project.boards = boards
    save_project(project)
    enqueue_sync(project_id, "project_saved", "полное сохранение проекта из UI")
    return project_to_client(project)


@router.post("/projects/{project_id}/nodes")
def post_node(project_id: str, body: CreateNodeBody) -> dict:
    project = require_project(project_id)
    try:
        add_node(project, body.parent_id, body.node_type, body.title, body.description)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    enqueue_sync(project_id, "tree_updated", f"новый узел: {body.title}")
    return project_to_client(project)


@router.patch("/projects/{project_id}/nodes/{node_id}")
def patch_node(project_id: str, node_id: str, body: UpdateNodeBody) -> dict:
    project = require_project(project_id)
    research_questions = None
    if body.research_questions is not None:
        research_questions = [
            MethodResearchQuestion(
                id=item.id or f"rq-{uuid4().hex[:8]}",
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
        update_node(
            project,
            node_id,
            title=body.title,
            description=body.description,
            research_questions=research_questions,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except StopIteration as e:
        raise HTTPException(404, "Node not found") from e
    if body.research_questions is not None:
        enqueue_sync(project_id, "research_updated", f"research_questions узла {node_id}")
    elif body.title is not None or body.description is not None:
        enqueue_sync(project_id, "tree_updated", f"обновлён узел {node_id}")
    return project_to_client(project)


@router.delete("/projects/{project_id}/nodes/{node_id}")
def remove_node(project_id: str, node_id: str) -> dict:
    project = require_project(project_id)
    try:
        delete_node(project, node_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except StopIteration as e:
        raise HTTPException(404, "Node not found") from e
    enqueue_sync(project_id, "tree_updated", f"удалён узел {node_id}")
    return project_to_client(project)


@router.post("/projects/{project_id}/boards/{board_id}/cards")
def post_card(project_id: str, board_id: str, body: CreateCardBody) -> dict:
    project = require_project(project_id)
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    card_id = f"c-{uuid4().hex[:8]}"
    card = ExperimentCard(
        id=card_id,
        board_id=board_id,
        column_id=body.column_id,
        title=body.title,
        description=body.description,
        tags=normalize_card_tags(body.tags),
        depends_on=_normalize_dep_ids(body.depends_on, {c.id for c in board.cards}, card_id),
    )
    register_project_card_tags(project, card.tags)
    board.cards.append(card)
    update_board(project, board)
    ensure_card_report(project, board_id, card.id, card.title)
    enqueue_sync(project_id, "kanban_updated", f"новая карточка: {card.title}")
    return project_to_client(project)


@router.patch("/projects/{project_id}/boards/{board_id}/cards/{card_id}")
def patch_card(
    project_id: str, board_id: str, card_id: str, body: UpdateCardBody
) -> dict:
    project = require_project(project_id)
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    card = next((c for c in board.cards if c.id == card_id), None)
    if card is None:
        raise HTTPException(404, "Card not found")
    old_title = card.title
    old_column = card.column_id
    deps_changed = False
    if body.title is not None:
        card.title = body.title
    if body.description is not None:
        card.description = body.description
    if body.column_id is not None:
        card.column_id = body.column_id
    if body.tags is not None:
        card.tags = normalize_card_tags(body.tags)
        register_project_card_tags(project, card.tags)
    if body.depends_on is not None:
        valid_ids = {c.id for c in board.cards}
        new_deps = _normalize_dep_ids(body.depends_on, valid_ids, card_id)
        if _would_create_cycle(board.cards, card_id, new_deps):
            raise HTTPException(400, "depends_on would create a cycle")
        card.depends_on = new_deps
        deps_changed = True
    update_board(project, board)
    if body.column_id is not None and body.column_id != old_column:
        if body.column_id != "done":
            enqueue_sync(
                project_id,
                "kanban_updated",
                f"карточка {card.title}: {old_column} → {body.column_id}",
            )
    elif deps_changed:
        enqueue_sync(project_id, "kanban_updated", f"связи DAG карточки {card.title}")
    elif body.title is not None or body.description is not None or body.tags is not None:
        enqueue_sync(project_id, "kanban_updated", f"правка карточки {card.title}")
    if body.title is not None and body.title != old_title:
        rename_report_for_card(project, board_id, card_id, card.title)
    return project_to_client(project)


@router.post("/projects/{project_id}/boards/{board_id}/dag/suggest")
def post_board_dag_suggest(
    project_id: str, board_id: str, body: DagSuggestBody
) -> dict:
    project = require_project(project_id)
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    suggestions = suggest_board_dag(project, board)
    if body.apply:
        updated = apply_dag_suggestions(board, suggestions)
        if updated:
            update_board(project, board)
            enqueue_sync(project_id, "kanban_updated", "применены предложения DAG")
        return {
            "suggestions": suggestions,
            "applied": updated,
            "project": project_to_client(project),
        }
    return {"suggestions": suggestions}


@router.delete("/projects/{project_id}/boards/{board_id}/cards/{card_id}")
def delete_card(project_id: str, board_id: str, card_id: str) -> dict:
    project = require_project(project_id)
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    board.cards = [c for c in board.cards if c.id != card_id]
    for other in board.cards:
        if card_id in (other.depends_on or []):
            other.depends_on = [d for d in other.depends_on if d != card_id]
    update_board(project, board)
    delete_report(project_id, card_id)
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

"""Project tree and kanban commands shared by HTTP and future entry points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from koi.adapters import card_reports, repository
from koi.core import project_ops
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
from koi.services.dag_suggest import normalize_dependency_ids, would_create_cycle
from koi.services import programs as program_service


class EntityNotFoundError(LookupError):
    """A project aggregate or one of its requested children does not exist."""


@dataclass(frozen=True)
class CreateProjectCommand:
    title: str
    project_id: str
    description: str = ""
    program_id: Optional[str] = None
    program_title: Optional[str] = None


@dataclass(frozen=True)
class CreateNodeCommand:
    parent_id: str
    node_type: NodeType
    title: str
    description: str = ""


@dataclass(frozen=True)
class ResearchQuestionInput:
    question: str
    id: Optional[str] = None
    answer: str = ""
    narrative: str = ""
    certainty: ResearchQuestionCertainty = ResearchQuestionCertainty.DEFINITE
    importance: int = 3
    card_id: Optional[str] = None


@dataclass(frozen=True)
class UpdateNodeCommand:
    title: Optional[str] = None
    description: Optional[str] = None
    research_questions: Optional[list[ResearchQuestionInput]] = None


@dataclass(frozen=True)
class CreateCardCommand:
    column_id: str
    title: str
    description: str = ""
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class UpdateCardCommand:
    title: Optional[str] = None
    description: Optional[str] = None
    column_id: Optional[str] = None
    tags: Optional[tuple[str, ...]] = None
    depends_on: Optional[tuple[str, ...]] = None


def _require_project(project_id: str) -> Project:
    project = repository.load_project(project_id, sync_reports=False)
    if project is None:
        raise EntityNotFoundError("Project not found")
    return project


def _require_board(project: Project, board_id: str) -> KanbanBoard:
    board = next((item for item in project.boards if item.id == board_id), None)
    if board is None:
        raise EntityNotFoundError("Board not found")
    return board


def _require_card(board: KanbanBoard, card_id: str) -> ExperimentCard:
    card = next((item for item in board.cards if item.id == card_id), None)
    if card is None:
        raise EntityNotFoundError("Card not found")
    return card


def _enqueue_sync(project_id: str, reason: str, detail: str) -> None:
    try:
        from koi.adapters.project_sync_queue import enqueue_push

        enqueue_push(project_id, reason, detail)
    except Exception:
        # Sync is best-effort and must not make a local edit fail.
        pass


def create_project(command: CreateProjectCommand) -> Project:
    if command.program_id and command.program_title:
        raise ValueError("Specify either program_id or program_title, not both")

    programs: list[str] = []
    if command.program_id:
        programs.append(command.program_id.strip())
    elif command.program_title:
        programs.append(program_service.create_program(command.program_title)["id"])

    return repository.create_project(
        command.title,
        project_id=command.project_id,
        description=command.description,
        programs=programs,
    )


def replace_project(project_id: str, snapshot: dict) -> Project:
    """Replace a project aggregate from the serialized UI snapshot."""
    existing = _require_project(project_id)
    project = Project(
        id=project_id,
        title=snapshot.get("title", existing.title),
        description=snapshot.get("description", existing.description),
    )

    project.nodes = [
        Node(
            id=raw["id"],
            project_id=project_id,
            parent_id=raw.get("parent_id"),
            node_type=NodeType(raw["node_type"]),
            title=raw["title"],
            description=raw.get("description", ""),
            verdict=Verdict(raw.get("verdict", "open")),
            research_questions=[
                MethodResearchQuestion(
                    id=item.get("id") or f"rq-{uuid4().hex[:8]}",
                    question=item["question"],
                    answer=item.get("answer", ""),
                    narrative=item.get("narrative", ""),
                    certainty=ResearchQuestionCertainty(
                        item.get(
                            "certainty",
                            ResearchQuestionCertainty.DEFINITE.value,
                        )
                    ),
                    importance=max(1, min(5, int(item.get("importance", 3)))),
                    card_id=item.get("card_id"),
                )
                for item in (raw.get("research_questions") or [])
            ],
        )
        for raw in snapshot.get("nodes", [])
    ]

    project.boards = [
        KanbanBoard(
            id=raw.get("id", board_id),
            owner_node_id=raw["owner_node_id"],
            columns=[
                KanbanColumn(**column) if isinstance(column, dict) else column
                for column in raw.get("columns", DEFAULT_KANBAN_COLUMNS)
            ],
            cards=[
                ExperimentCard(**card)
                for card in raw.get("cards", [])
            ],
        )
        for board_id, raw in snapshot.get("boards", {}).items()
    ]

    repository.save_project(project)
    _enqueue_sync(project_id, "project_saved", "полное сохранение проекта из UI")
    return project


def create_node(project_id: str, command: CreateNodeCommand) -> Project:
    project = _require_project(project_id)
    project_ops.add_node(
        project,
        command.parent_id,
        command.node_type,
        command.title,
        command.description,
    )
    repository.save_project(project)
    _enqueue_sync(project_id, "tree_updated", f"новый узел: {command.title}")
    return project


def update_node(project_id: str, node_id: str, command: UpdateNodeCommand) -> Project:
    project = _require_project(project_id)
    questions = None
    if command.research_questions is not None:
        questions = [
            MethodResearchQuestion(
                id=item.id or f"rq-{uuid4().hex[:8]}",
                question=item.question,
                answer=item.answer,
                narrative=item.narrative,
                certainty=item.certainty,
                importance=item.importance,
                card_id=item.card_id,
            )
            for item in command.research_questions
        ]
    try:
        project_ops.update_node(
            project,
            node_id,
            title=command.title,
            description=command.description,
            research_questions=questions,
        )
    except StopIteration as exc:
        raise EntityNotFoundError("Node not found") from exc

    repository.save_project(project)
    if command.research_questions is not None:
        _enqueue_sync(project_id, "research_updated", f"research_questions узла {node_id}")
    elif command.title is not None or command.description is not None:
        _enqueue_sync(project_id, "tree_updated", f"обновлён узел {node_id}")
    return project


def delete_node(project_id: str, node_id: str) -> Project:
    project = _require_project(project_id)
    try:
        project_ops.delete_node(project, node_id)
    except StopIteration as exc:
        raise EntityNotFoundError("Node not found") from exc
    repository.save_project(project)
    _enqueue_sync(project_id, "tree_updated", f"удалён узел {node_id}")
    return project


def create_card(project_id: str, board_id: str, command: CreateCardCommand) -> Project:
    project = _require_project(project_id)
    board = _require_board(project, board_id)
    card_id = f"c-{uuid4().hex[:8]}"
    card = ExperimentCard(
        id=card_id,
        board_id=board_id,
        column_id=command.column_id,
        title=command.title,
        description=command.description,
        tags=normalize_card_tags(list(command.tags)),
        depends_on=normalize_dependency_ids(
            list(command.depends_on),
            {item.id for item in board.cards},
            card_id,
        ),
    )
    register_project_card_tags(project, card.tags)
    board.cards.append(card)
    repository.save_project(project)
    card_reports.ensure_card_report(project, board_id, card.id, card.title)
    _enqueue_sync(project_id, "kanban_updated", f"новая карточка: {card.title}")
    return project


def update_card(
    project_id: str,
    board_id: str,
    card_id: str,
    command: UpdateCardCommand,
) -> Project:
    project = _require_project(project_id)
    board = _require_board(project, board_id)
    card = _require_card(board, card_id)
    old_title = card.title
    old_column = card.column_id
    dependencies_changed = False

    if command.title is not None:
        card.title = command.title
    if command.description is not None:
        card.description = command.description
    if command.column_id is not None:
        card.column_id = command.column_id
    if command.tags is not None:
        card.tags = normalize_card_tags(list(command.tags))
        register_project_card_tags(project, card.tags)
    if command.depends_on is not None:
        dependencies = normalize_dependency_ids(
            list(command.depends_on),
            {item.id for item in board.cards},
            card_id,
        )
        if would_create_cycle(board.cards, card_id, dependencies):
            raise ValueError("depends_on would create a cycle")
        card.depends_on = dependencies
        dependencies_changed = True

    repository.save_project(project)
    if command.column_id is not None and command.column_id != old_column:
        if command.column_id != "done":
            _enqueue_sync(
                project_id,
                "kanban_updated",
                f"карточка {card.title}: {old_column} → {command.column_id}",
            )
    elif dependencies_changed:
        _enqueue_sync(project_id, "kanban_updated", f"связи DAG карточки {card.title}")
    elif command.title is not None or command.description is not None or command.tags is not None:
        _enqueue_sync(project_id, "kanban_updated", f"правка карточки {card.title}")

    if command.title is not None and command.title != old_title:
        card_reports.rename_report_for_card(project, board_id, card_id, card.title)
    return project


def delete_card(project_id: str, board_id: str, card_id: str) -> Project:
    project = _require_project(project_id)
    board = _require_board(project, board_id)
    board.cards = [card for card in board.cards if card.id != card_id]
    for card in board.cards:
        if card_id in (card.depends_on or []):
            card.depends_on = [
                dependency
                for dependency in card.depends_on
                if dependency != card_id
            ]
    repository.save_project(project)
    card_reports.delete_report(project_id, card_id)
    return project

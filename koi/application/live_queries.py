"""Application queries for running-card activity and live artifacts."""

from __future__ import annotations

from pathlib import Path

from koi.adapters import repository
from koi.core.models import ExperimentCard, KanbanBoard, Project
from koi.services import card_live, rq_discoveries


class EntityNotFoundError(LookupError):
    """A project, board, or card required by a live query is missing."""


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


def running_activity(project_id: str) -> list[dict]:
    _require_project(project_id)
    return rq_discoveries.running_kanban_activity(project_id)


def live_monitor(project_id: str) -> list[dict]:
    project = _require_project(project_id)
    return card_live.live_monitor_cards(project_id, project)


def card_snapshot(
    project_id: str,
    board_id: str,
    card_id: str,
    *,
    tail_lines: int = 100,
) -> dict:
    project = _require_project(project_id)
    board = _require_board(project, board_id)
    card = _require_card(board, card_id)
    hints = card_live.merge_live_hints(
        project,
        board_id,
        card_id,
        card.title,
        card.description,
    )
    snapshot = card_live.live_snapshot(
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


def resolve_live_file(project_id: str, path: str) -> Path:
    _require_project(project_id)
    resolved = card_live.resolve_project_path(project_id, path)
    if not resolved.is_file():
        raise FileNotFoundError("File not found")
    return resolved

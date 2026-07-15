"""Project report use cases and report-asset access."""

from __future__ import annotations

from pathlib import Path

from koi.adapters import card_reports, repository
from koi.core.models import ExperimentCard, KanbanBoard, Project


class EntityNotFoundError(LookupError):
    """A project, board, or card required by a report use case is missing."""


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


def _load_card(project_id: str, board_id: str, card_id: str) -> tuple[Project, ExperimentCard]:
    project = _require_project(project_id)
    board = _require_board(project, board_id)
    return project, _require_card(board, card_id)


def _enqueue_sync(project_id: str, reason: str, detail: str) -> None:
    try:
        from koi.adapters.project_sync_queue import enqueue_push

        enqueue_push(project_id, reason, detail)
    except Exception:
        # Report persistence must remain available when git sync is unavailable.
        pass


def read_card_report(project_id: str, board_id: str, card_id: str) -> dict:
    project = _require_project(project_id)
    board = _require_board(project, board_id)
    card = next((item for item in board.cards if item.id == card_id), None)
    if card is not None:
        return card_reports.read_report(
            project,
            board_id,
            card_id,
            card.title,
        )
    indexed = card_reports.read_report_indexed(project_id, card_id)
    if indexed is not None:
        return indexed
    raise EntityNotFoundError("Card not found")


def ensure_report_card(project_id: str, board_id: str, card_id: str) -> None:
    """Validate report ownership before an HTTP adapter reads an upload body."""
    _load_card(project_id, board_id, card_id)


def card_report_path(project_id: str, board_id: str, card_id: str) -> dict:
    project, card = _load_card(project_id, board_id, card_id)
    return card_reports.report_path_info(
        project,
        board_id,
        card_id,
        card.title,
    )


def write_card_report(
    project_id: str,
    board_id: str,
    card_id: str,
    content: str,
) -> dict:
    project, card = _load_card(project_id, board_id, card_id)
    result = card_reports.write_report(
        project,
        board_id,
        card_id,
        card.title,
        content,
    )
    _enqueue_sync(project_id, "report_saved", f"отчёт карточки {card.title}")
    return result


def store_report_asset(
    project_id: str,
    board_id: str,
    card_id: str,
    data: bytes,
    content_type: str,
) -> dict:
    project, card = _load_card(project_id, board_id, card_id)
    return card_reports.save_report_asset(
        project,
        board_id,
        card_id,
        card.title,
        data,
        content_type,
    )


def report_asset_path(
    project_id: str,
    board_id: str,
    card_id: str,
    asset_name: str,
) -> Path:
    project, card = _load_card(project_id, board_id, card_id)
    return card_reports.resolve_report_asset_path(
        project,
        board_id,
        card_id,
        card.title,
        asset_name,
    )

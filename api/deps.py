"""Shared FastAPI dependencies and helpers."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from koi.core.models import ExperimentCard, KanbanBoard, Project
from koi.adapters.repository import load_project
from koi.adapters.paths import koi_root
from koi.adapters.workspace import get_workspace


def enqueue_sync(project_id: str, reason: str, detail: str) -> None:
    try:
        from koi.adapters.project_sync_queue import enqueue_push

        enqueue_push(project_id, reason, detail)
    except Exception:
        pass


def get_project(project_id: str, *, sync_reports: bool = False) -> Project:
    project = load_project(project_id, sync_reports=sync_reports)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def parse_project(project_id: str) -> Project:
    """Parse project.md without syncing all report files."""
    return get_project(project_id, sync_reports=False)


def workspace_relative(path: Path) -> str:
    try:
        project_id = path.parts[path.parts.index("koi-structure") - 1]
    except (ValueError, IndexError):
        project_id = None
    if project_id:
        try:
            root = koi_root(project_id).resolve()
            return str(path.resolve().relative_to(root))
        except (KeyError, ValueError):
            pass
    ws = get_workspace().engine_root
    try:
        return str(path.resolve().relative_to(ws.resolve()))
    except ValueError:
        return str(path)


def find_card(
    project: Project, board_id: str, card_id: str
) -> tuple[KanbanBoard, ExperimentCard]:
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise HTTPException(404, "Board not found")
    card = next((c for c in board.cards if c.id == card_id), None)
    if card is None:
        raise HTTPException(404, "Card not found")
    return board, card

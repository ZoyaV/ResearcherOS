"""Tests for project.md kanban parsing and normalization."""

from __future__ import annotations

from koi.core.md_io import normalize_kanban_board, parse_project_md, serialize_project_md
from koi.core.migrate import kanban_md_needs_upgrade
from koi.core.models import DEFAULT_KANBAN_COLUMNS, ExperimentCard, KanbanBoard


def test_kanban_md_needs_upgrade() -> None:
    old = "| backlog | running | done |\n"
    new = "| backlog | running | done | successful |\n"
    assert kanban_md_needs_upgrade(old) is True
    assert kanban_md_needs_upgrade(new) is False
    assert kanban_md_needs_upgrade("# no kanban\n") is False


def test_default_kanban_has_successful_column() -> None:
    col_ids = [c.id for c in DEFAULT_KANBAN_COLUMNS]
    assert col_ids == ["backlog", "running", "done", "successful"]


def test_normalize_kanban_adds_successful_column() -> None:
    board = KanbanBoard(
        id="board-test",
        owner_node_id="m-test",
        columns=DEFAULT_KANBAN_COLUMNS[:3],
        cards=[
            ExperimentCard(
                id="c1",
                board_id="board-test",
                column_id="done",
                title="Finished",
            )
        ],
    )
    normalized = normalize_kanban_board(board)
    assert [c.id for c in normalized.columns] == ["backlog", "running", "done", "successful"]
    assert normalized.cards[0].column_id == "done"


def test_roundtrip_preserves_successful_cards() -> None:
    text = """---
id: proj-test
title: Test
---
# problem: root

Root

#### method: m1

Method

<!-- koi:kanban board-m1 -->
| backlog | running | done | successful |
| --- | --- | --- | --- |
| | | Old done <!-- id:c-old desc:report ready --> | Winner <!-- id:c-win desc:confirmed --> |
"""
    project = parse_project_md(text, project_id="proj-test")
    board = project.boards[0]
    assert [c.id for c in board.columns] == ["backlog", "running", "done", "successful"]
    by_id = {c.id: c.column_id for c in board.cards}
    assert by_id["c-old"] == "done"
    assert by_id["c-win"] == "successful"

    reserialized = serialize_project_md(project)
    reloaded = parse_project_md(reserialized, project_id="proj-test")
    reloaded_by_id = {c.id: c.column_id for c in reloaded.boards[0].cards}
    assert reloaded_by_id == by_id

"""Card timestamp scrubbing — filesystem mtime is not card edit time."""

from __future__ import annotations

from pathlib import Path

from koi.adapters import card_reports
from koi.core.models import (
    DEFAULT_KANBAN_COLUMNS,
    ExperimentCard,
    KanbanBoard,
    Node,
    NodeType,
    Project,
)


def _project_with_cards(project_id: str, cards: list[ExperimentCard]) -> Project:
    return Project(
        id=project_id,
        title="TS",
        nodes=[
            Node(
                id="m1",
                project_id=project_id,
                parent_id=None,
                node_type=NodeType.METHOD,
                title="Method",
            )
        ],
        boards=[
            KanbanBoard(
                id="board-m1",
                owner_node_id="m1",
                columns=list(DEFAULT_KANBAN_COLUMNS),
                cards=cards,
            )
        ],
    )


def test_enrich_missing_card_timestamps_is_noop() -> None:
    project = _project_with_cards(
        "proj-noop",
        [
            ExperimentCard(
                id="c-old",
                board_id="board-m1",
                column_id="backlog",
                title="Legacy",
            )
        ],
    )
    assert card_reports.enrich_missing_card_timestamps(project) is False
    assert project.boards[0].cards[0].updated_at is None


def test_scrub_drops_duplicate_bulk_stamps(tmp_path: Path, monkeypatch) -> None:
    project_id = "proj-bulk"
    bulk = "2026-08-06T08:13:27Z"
    project = _project_with_cards(
        project_id,
        [
            ExperimentCard(
                id="c1",
                board_id="board-m1",
                column_id="backlog",
                title="A",
                created_at=bulk,
                updated_at=bulk,
            ),
            ExperimentCard(
                id="c2",
                board_id="board-m1",
                column_id="backlog",
                title="B",
                created_at=bulk,
                updated_at=bulk,
            ),
            ExperimentCard(
                id="c-real",
                board_id="board-m1",
                column_id="done",
                title="Real",
                created_at="2026-08-06T17:19:58Z",
                updated_at="2026-08-06T18:26:08Z",
            ),
        ],
    )
    monkeypatch.setattr(
        "koi.adapters.paths.project_md",
        lambda _pid: tmp_path / "project.md",
    )

    assert card_reports.scrub_filesystem_echo_timestamps(project) is True
    by_id = {c.id: c for c in project.boards[0].cards}
    assert by_id["c1"].updated_at is None
    assert by_id["c2"].updated_at is None
    assert by_id["c-real"].created_at == "2026-08-06T17:19:58Z"
    assert by_id["c-real"].updated_at == "2026-08-06T18:26:08Z"


def test_scrub_keeps_unique_updated_when_created_is_bulk(
    tmp_path: Path, monkeypatch
) -> None:
    project_id = "proj-partial"
    bulk = "2026-07-31T13:49:24Z"
    project = _project_with_cards(
        project_id,
        [
            ExperimentCard(
                id="c-a",
                board_id="board-m1",
                column_id="done",
                title="A",
                created_at=bulk,
                updated_at="2026-08-06T17:19:58Z",
            ),
            ExperimentCard(
                id="c-b",
                board_id="board-m1",
                column_id="done",
                title="B",
                created_at=bulk,
                updated_at=bulk,
            ),
        ],
    )
    monkeypatch.setattr(
        "koi.adapters.paths.project_md",
        lambda _pid: tmp_path / "project.md",
    )

    assert card_reports.scrub_filesystem_echo_timestamps(project) is True
    by_id = {c.id: c for c in project.boards[0].cards}
    assert by_id["c-a"].created_at is None
    assert by_id["c-a"].updated_at == "2026-08-06T17:19:58Z"
    assert by_id["c-b"].created_at is None
    assert by_id["c-b"].updated_at is None


def test_merge_prefers_stored_over_filesystem() -> None:
    created, updated = card_reports.merge_card_activity_timestamps(
        "2026-08-01T10:00:00Z",
        "2026-08-01T10:00:00Z",
        "2026-07-01T10:00:00Z",
        "2026-08-07T12:00:00Z",
    )
    assert created == "2026-08-01T10:00:00Z"
    assert updated == "2026-08-01T10:00:00Z"

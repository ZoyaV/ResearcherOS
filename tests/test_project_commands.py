"""Unit tests for project and kanban application commands."""

from __future__ import annotations

import pytest

from koi.application import project_commands
from koi.core.models import ExperimentCard, KanbanBoard, Node, NodeType, Project


@pytest.fixture
def project() -> Project:
    board = KanbanBoard(
        id="board-method",
        owner_node_id="method",
        cards=[
            ExperimentCard(
                id="card-a",
                board_id="board-method",
                column_id="backlog",
                title="Card A",
            ),
            ExperimentCard(
                id="card-b",
                board_id="board-method",
                column_id="backlog",
                title="Card B",
                depends_on=["card-a"],
            ),
        ],
    )
    return Project(
        id="demo",
        title="Demo",
        nodes=[
            Node(
                id="problem",
                project_id="demo",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="Problem",
            ),
            Node(
                id="method",
                project_id="demo",
                parent_id="problem",
                node_type=NodeType.METHOD,
                title="Method",
            ),
        ],
        boards=[board],
    )


@pytest.fixture
def command_context(monkeypatch, project: Project) -> dict[str, list]:
    calls: dict[str, list] = {
        "saved_projects": [],
        "reports": [],
        "renames": [],
        "deletions": [],
        "sync": [],
    }
    monkeypatch.setattr(
        project_commands.repository,
        "load_project",
        lambda project_id, *, sync_reports=False: project if project_id == project.id else None,
    )
    monkeypatch.setattr(
        project_commands.repository,
        "save_project",
        lambda loaded: calls["saved_projects"].append(loaded),
    )
    monkeypatch.setattr(
        project_commands.card_reports,
        "ensure_card_report",
        lambda *args: calls["reports"].append(args),
    )
    monkeypatch.setattr(
        project_commands.card_reports,
        "rename_report_for_card",
        lambda *args: calls["renames"].append(args),
    )
    monkeypatch.setattr(
        project_commands.card_reports,
        "delete_report",
        lambda *args: calls["deletions"].append(args),
    )
    monkeypatch.setattr(
        project_commands,
        "_enqueue_sync",
        lambda *args: calls["sync"].append(args),
    )
    return calls


def test_create_card_coordinates_domain_persistence_and_report(
    project: Project,
    command_context: dict[str, list],
) -> None:
    result = project_commands.create_card(
        "demo",
        "board-method",
        project_commands.CreateCardCommand(
            column_id="backlog",
            title="Card C",
            tags=("baseline", "baseline", "bad tag"),
            depends_on=("card-a", "missing"),
        ),
    )

    card = result.boards[0].cards[-1]
    assert card.title == "Card C"
    assert card.tags == ["baseline"]
    assert card.depends_on == ["card-a"]
    assert result.card_tags == ["baseline"]
    assert command_context["saved_projects"] == [project]
    assert command_context["reports"][0][2] == card.id
    assert command_context["sync"] == [
        ("demo", "kanban_updated", "новая карточка: Card C")
    ]


def test_update_card_rejects_dependency_cycle(
    project: Project,
    command_context: dict[str, list],
) -> None:
    with pytest.raises(ValueError, match="would create a cycle"):
        project_commands.update_card(
            "demo",
            "board-method",
            "card-a",
            project_commands.UpdateCardCommand(depends_on=("card-b",)),
        )

    assert command_context["saved_projects"] == []


def test_update_card_renames_report_and_enqueues_edit(
    project: Project,
    command_context: dict[str, list],
) -> None:
    result = project_commands.update_card(
        "demo",
        "board-method",
        "card-a",
        project_commands.UpdateCardCommand(title="Renamed"),
    )

    assert result.boards[0].cards[0].title == "Renamed"
    assert command_context["renames"][0][2:] == ("card-a", "Renamed")
    assert command_context["sync"] == [
        ("demo", "kanban_updated", "правка карточки Renamed")
    ]


def test_delete_card_removes_incoming_dependencies(
    project: Project,
    command_context: dict[str, list],
) -> None:
    result = project_commands.delete_card("demo", "board-method", "card-a")

    assert [card.id for card in result.boards[0].cards] == ["card-b"]
    assert result.boards[0].cards[0].depends_on == []
    assert command_context["deletions"] == [("demo", "card-a")]


def test_create_node_uses_repository_rule_and_enqueues_sync(
    project: Project,
    command_context: dict[str, list],
) -> None:
    result = project_commands.create_node(
        "demo",
        project_commands.CreateNodeCommand(
            parent_id="problem",
            node_type=NodeType.CAUSE,
            title="Cause",
        ),
    )

    assert result.nodes[-1].node_type == NodeType.CAUSE
    assert command_context["sync"] == [
        ("demo", "tree_updated", "новый узел: Cause")
    ]


def test_missing_project_and_board_have_application_errors(
    command_context: dict[str, list],
) -> None:
    with pytest.raises(project_commands.EntityNotFoundError, match="Project"):
        project_commands.delete_node("missing", "node")
    with pytest.raises(project_commands.EntityNotFoundError, match="Board"):
        project_commands.delete_card("demo", "missing", "card")

"""Unit tests for project and kanban application commands."""

from __future__ import annotations

import pytest

from koi.application import project_commands
from koi.core.models import (
    ExperimentCard,
    KanbanBoard,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
)


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
        "created_projects": [],
        "saved_projects": [],
        "updated_boards": [],
        "reports": [],
        "renames": [],
        "deletions": [],
        "sync": [],
    }
    monkeypatch.setattr(
        project_commands.repository,
        "create_project",
        lambda *args, **kwargs: calls["created_projects"].append((args, kwargs))
        or project,
    )
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
        project_commands.repository,
        "update_board",
        lambda loaded, board: calls["updated_boards"].append((loaded, board))
        or board,
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


def test_create_project_resolves_program_title_and_delegates_to_repository(
    project: Project,
    command_context: dict[str, list],
) -> None:
    result = project_commands.create_project(
        project_commands.CreateProjectCommand(
            title="Demo",
            project_id="demo",
            description="  Description  ",
            program_title="Embodied AI",
        )
    )

    assert result is project
    assert command_context["created_projects"] == [
        (
            ("Demo",),
            {
                "project_id": "demo",
                "description": "  Description  ",
                "programs": ["embodied-ai"],
            },
        )
    ]


def test_create_project_rejects_program_id_and_title_together(
    command_context: dict[str, list],
) -> None:
    with pytest.raises(ValueError, match="Specify either program_id or program_title"):
        project_commands.create_project(
            project_commands.CreateProjectCommand(
                title="Demo",
                project_id="demo",
                program_id="existing",
                program_title="New program",
            )
        )

    assert command_context["created_projects"] == []


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


def test_replace_project_rebuilds_snapshot_and_enqueues_sync(
    project: Project,
    command_context: dict[str, list],
) -> None:
    result = project_commands.replace_project(
        "demo",
        {
            "title": "Replaced",
            "description": "Snapshot from UI",
            "nodes": [
                {
                    "id": "method-new",
                    "parent_id": None,
                    "node_type": "method",
                    "title": "New method",
                    "verdict": "open",
                    "research_questions": [
                        {
                            "question": "What changed?",
                            "certainty": "tentative",
                            "importance": 9,
                        }
                    ],
                }
            ],
            "boards": {
                "board-new": {
                    "owner_node_id": "method-new",
                    "columns": [
                        {"id": "backlog", "title": "Backlog", "order": 0}
                    ],
                    "cards": [
                        {
                            "id": "card-new",
                            "board_id": "board-new",
                            "column_id": "backlog",
                            "title": "New card",
                        }
                    ],
                }
            },
        },
    )

    assert result.title == "Replaced"
    assert result.description == "Snapshot from UI"
    assert result.nodes[0].project_id == "demo"
    question = result.nodes[0].research_questions[0]
    assert question.id.startswith("rq-")
    assert question.certainty == ResearchQuestionCertainty.TENTATIVE
    assert question.importance == 5
    assert result.boards[0].id == "board-new"
    assert result.boards[0].cards[0].title == "New card"
    assert command_context["saved_projects"] == [result]
    assert command_context["sync"] == [
        ("demo", "project_saved", "полное сохранение проекта из UI")
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


def test_suggest_board_dependencies_applies_persists_and_enqueues_sync(
    project: Project,
    command_context: dict[str, list],
    monkeypatch,
) -> None:
    suggestions = [
        {
            "from_card_id": "card-a",
            "to_card_id": "card-b",
            "confidence": 0.8,
        }
    ]
    monkeypatch.setattr(
        project_commands,
        "suggest_board_dag",
        lambda loaded, board: suggestions,
    )
    monkeypatch.setattr(
        project_commands,
        "apply_dag_suggestions",
        lambda board, items: 1,
    )

    result = project_commands.suggest_board_dependencies(
        "demo",
        "board-method",
        apply=True,
    )

    assert result.project is project
    assert result.suggestions == suggestions
    assert result.applied == 1
    assert command_context["updated_boards"] == [(project, project.boards[0])]
    assert command_context["sync"] == [
        ("demo", "kanban_updated", "применены предложения DAG")
    ]


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

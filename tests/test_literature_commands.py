"""Unit tests for literature application commands."""

from __future__ import annotations

from koi.application import literature_commands
from koi.core import project_ops
from koi.core.models import Node, NodeType, Project


def test_create_review_set_builds_project_tree_cards_and_reports(monkeypatch) -> None:
    project = Project(
        id="review-demo",
        title="Review Set",
        nodes=[
            Node(
                id="problem",
                project_id="review-demo",
                node_type=NodeType.PROBLEM,
                title="Review Set",
            )
        ],
    )
    saved: list[Project] = []
    updated_boards = []
    reports = []
    card_ids = iter(("card-1", "card-2"))

    monkeypatch.setattr(
        literature_commands.repository,
        "create_project",
        lambda title: project,
    )
    monkeypatch.setattr(
        literature_commands.repository,
        "save_project",
        lambda item: saved.append(item),
    )
    monkeypatch.setattr(
        literature_commands.repository,
        "add_node",
        lambda item, parent_id, node_type, title, description="": project_ops.add_node(
            item, parent_id, node_type, title, description
        ),
    )
    monkeypatch.setattr(
        literature_commands.repository,
        "update_board",
        lambda item, board: updated_boards.append(board) or board,
    )
    monkeypatch.setattr(
        literature_commands.card_reports,
        "write_report",
        lambda *args: reports.append(args),
    )
    monkeypatch.setattr(
        literature_commands.literature,
        "review_card_id",
        lambda: next(card_ids),
    )

    papers = [
        {
            "title": "Paper A",
            "arxiv_url": "https://arxiv.org/abs/1",
            "score": 2.0,
            "matched_terms": ["agent"],
            "abstract": "A",
        },
        {
            "title": "Paper B",
            "arxiv_url": "https://arxiv.org/abs/2",
            "score": 1.0,
            "matched_terms": [],
            "abstract": "B",
        },
    ]
    result = literature_commands.create_review_set(
        literature_commands.CreateReviewSetCommand(
            query="  embodied agents  ",
            limit=10,
            papers=papers,
        )
    )

    assert result.project is project
    assert result.query == "embodied agents"
    assert result.count == 2
    assert "2 ranked paper candidates" in project.description
    assert [node.node_type for node in project.nodes] == [
        NodeType.PROBLEM,
        NodeType.CAUSE,
        NodeType.CAUSE_EVIDENCE,
        NodeType.METHOD,
    ]
    assert [card.id for card in project.boards[0].cards] == ["card-1", "card-2"]
    assert [card.title for card in project.boards[0].cards] == ["Paper A", "Paper B"]
    assert saved == [project]
    assert updated_boards == [project.boards[0]]
    assert len(reports) == 2
    assert reports[0][3] == "Paper A"
    assert "Query: embodied agents" in reports[0][4]


def test_create_review_set_searches_when_papers_are_not_supplied(monkeypatch) -> None:
    monkeypatch.setattr(
        literature_commands.literature,
        "search_library",
        lambda query, limit: [],
    )

    try:
        literature_commands.create_review_set(
            literature_commands.CreateReviewSetCommand(query="question", limit=3)
        )
    except ValueError as error:
        assert str(error) == "No ranked papers available for this query"
    else:
        raise AssertionError("Expected an empty review set to be rejected")

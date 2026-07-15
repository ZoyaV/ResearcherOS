"""Contract tests for project read models shared by API and Hub."""

from __future__ import annotations

from importlib import import_module

from koi.application.project_views import allowed_children, project_to_client
from koi.core.models import (
    ExperimentCard,
    KanbanBoard,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
)


def test_project_to_client_builds_frontend_read_model() -> None:
    method = Node(
        id="method",
        project_id="demo",
        parent_id="evidence",
        node_type=NodeType.METHOD,
        title="Method",
        research_questions=[
            MethodResearchQuestion(
                id="rq-1",
                question="Did it work?",
                certainty=ResearchQuestionCertainty.TENTATIVE,
                card_id="card-1",
            )
        ],
    )
    board = KanbanBoard(
        id="board-method",
        owner_node_id=method.id,
        cards=[
            ExperimentCard(
                id="card-1",
                board_id="board-method",
                column_id="done",
                title="Experiment",
            )
        ],
    )
    project = Project(id="demo", title="Demo", nodes=[method], boards=[board])

    payload = project_to_client(project)

    node = payload["nodes"][0]
    assert node["has_kanban"] is True
    assert node["board_id"] == "board-method"
    assert node["research_question_counts"] == {"definite": 0, "tentative": 1}
    assert node["research_questions"][0]["card_title"] == "Experiment"
    assert payload["boards"]["board-method"]["source_project_id"] == "demo"


def test_allowed_children_exposes_domain_rules_as_values() -> None:
    assert allowed_children("cause") == ["cause_evidence", "remediation"]
    assert allowed_children("method") == []


def test_legacy_api_helper_imports_remain_compatible() -> None:
    root_helpers = import_module("koi.api_helpers")
    service_helpers = import_module("koi.services.api_helpers")

    assert root_helpers.project_to_client is project_to_client
    assert service_helpers.allowed_children is allowed_children

"""Contract tests for project read models shared by API and Hub."""

from __future__ import annotations

from importlib import import_module

from koi.projects.views import allowed_children, project_to_client
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


def test_service_api_helper_import_remains_compatible() -> None:
    service_helpers = import_module("koi.services.api_helpers")

    assert service_helpers.allowed_children is allowed_children


def test_legacy_application_imports_remain_compatible() -> None:
    module_pairs = (
        ("koi.application.project_commands", "koi.projects.commands"),
        ("koi.application.project_views", "koi.projects.views"),
        ("koi.application.report_commands", "koi.projects.reports"),
        ("koi.application.live_queries", "koi.projects.live"),
    )

    for legacy_name, canonical_name in module_pairs:
        assert import_module(legacy_name) is import_module(canonical_name)

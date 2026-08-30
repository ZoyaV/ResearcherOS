"""Behavior contracts for the knowledge capability before restructuring it."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from koi.core.models import (
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
    Verdict,
)


knowledge = importlib.import_module("koi.knowledge")
knowledge_store = importlib.import_module("koi.knowledge.store")


@pytest.fixture
def knowledge_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    project_root = tmp_path / "demo"
    reports = project_root / "reports"
    reports.mkdir(parents=True)
    (reports / "index.json").write_text(
        json.dumps({"card-1": "cause/card-1.run.md"}), encoding="utf-8"
    )

    monkeypatch.setattr(
        knowledge_store,
        "project_knowledge_path",
        lambda _project_id: project_root / "KNOWLEDGE.md",
    )
    monkeypatch.setattr(
        knowledge_store,
        "project_knowledge_log_path",
        lambda _project_id: project_root / "KNOWLEDGE_LOG.md",
    )
    monkeypatch.setattr(
        knowledge_store,
        "project_knowledge_dir",
        lambda _project_id: project_root / "knowledge",
    )
    monkeypatch.setattr(knowledge_store, "reports_dir", lambda _project_id: reports)

    return Project(
        id="demo",
        title="Demo project",
        nodes=[
            Node(
                id="problem-1",
                project_id="demo",
                node_type=NodeType.PROBLEM,
                title="Problem",
                description="A reproducible problem.",
            ),
            Node(
                id="cause-1",
                project_id="demo",
                parent_id="problem-1",
                node_type=NodeType.CAUSE,
                title="Cause hypothesis",
                description="The suspected mechanism.",
                verdict=Verdict.SUPPORTED,
            ),
            Node(
                id="remediation-1",
                project_id="demo",
                parent_id="cause-1",
                node_type=NodeType.REMEDIATION,
                title="Remediation",
            ),
            Node(
                id="method-1",
                project_id="demo",
                parent_id="remediation-1",
                node_type=NodeType.METHOD,
                title="Controlled benchmark",
                research_questions=[
                    MethodResearchQuestion(
                        id="rq-1",
                        question="Did the metric improve?",
                        answer="metric +12%",
                        narrative="The metric improved by twelve percent.",
                        certainty=ResearchQuestionCertainty.DEFINITE,
                        importance=5,
                        card_id="card-1",
                    )
                ],
            ),
        ],
    )


def test_hypotheses_markdown_contract(knowledge_project: Project) -> None:
    markdown = knowledge.render_hypotheses_doc(
        knowledge_project, {"card-1": "cause/card-1.run.md"}
    )

    assert markdown == """# Hypotheses and results

Automatically generated summary of 1 hypotheses (supported: 1, refuted: 0, open: 0; insights: 1). Sources: project.md and research.json. Rebuilt whenever the project is saved; do not edit manually.

## Cause hypothesis

Verdict: ✔ supported  ·  node `cause-1`

The suspected mechanism.

- Did the metric improve?
  - The metric improved by twelve percent.  _(certainty: definite, importance: 5/5; method `method-1`, card `card-1` → [report](../reports/cause/card-1.run.md))_
"""


def test_summary_contract_includes_docs_insights_and_reports(
    knowledge_project: Project,
) -> None:
    knowledge.write_project_knowledge(knowledge_project)

    summary = knowledge.knowledge_summary(knowledge_project)

    assert summary["stats"] == {
        "hypotheses": 1,
        "supported": 1,
        "refuted": 0,
        "open": 0,
        "insights": 1,
        "docs": 1,
        "reports": 1,
        "pages": 0,
    }
    assert summary["docs"][0]["path"] == "knowledge/hypotheses.md"
    assert summary["docs"][0]["generated"] is True
    assert summary["hypotheses"][0]["insights"][0]["report"] == (
        "reports/cause/card-1.run.md"
    )


def test_write_is_idempotent_and_logs_verdict_changes(
    knowledge_project: Project,
) -> None:
    knowledge.write_project_knowledge(knowledge_project)
    log_path = knowledge.knowledge_log_path(knowledge_project.id)
    initial_log = log_path.read_text(encoding="utf-8")

    knowledge.write_project_knowledge(knowledge_project)

    assert log_path.read_text(encoding="utf-8") == initial_log

    cause = next(node for node in knowledge_project.nodes if node.id == "cause-1")
    cause.verdict = Verdict.REFUTED
    knowledge.write_project_knowledge(knowledge_project)

    updated_log = log_path.read_text(encoding="utf-8")
    assert "✔ supported → ✗ refuted" in updated_log
    assert updated_log.count("# Knowledge base log: Demo project") == 1


def test_service_import_remains_compatible() -> None:
    assert importlib.import_module("koi.services.knowledge") is knowledge

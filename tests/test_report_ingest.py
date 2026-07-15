"""Behavior contracts for report parsing and ingestion."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from koi.core.models import (
    ExperimentCard,
    KanbanBoard,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    Verdict,
)
from koi.projects import report_ingest


workflow = importlib.import_module("koi.projects.report_ingest.workflow")


def _report(*, verdict_node: str = "cause-new", json_body: str | None = None) -> str:
    body = json_body or """[
  {
    "method_id": "method-1",
    "card_id": "card-1",
    "question": "Did it work?",
    "answer": "yes",
    "narrative": "The metric improved.",
    "certainty": "definite",
    "importance": 7
  }
]"""
    return f"""## 0. Привязка

| Поле | Значение |
| --- | --- |
| Гипотеза | `cause-old` |
| Метод / карточка | `method-1` / `card-1` |

## 5. Заявка в базу знаний

### 5.1 Вердикт

`{verdict_node}` → result **supported**

### 5.2 Инсайты

```json
{body}
```
"""


def _project() -> Project:
    return Project(
        id="demo",
        title="Demo",
        nodes=[
            Node(
                id="cause-new",
                project_id="demo",
                node_type=NodeType.CAUSE,
                title="Cause",
            ),
            Node(
                id="method-1",
                project_id="demo",
                parent_id="cause-new",
                node_type=NodeType.METHOD,
                title="Method",
                research_questions=[
                    MethodResearchQuestion(
                        id="keep-1", question="Other card", card_id="card-2"
                    ),
                    MethodResearchQuestion(
                        id="replace-1", question="Old", card_id="card-1"
                    ),
                ],
            ),
        ],
        boards=[
            KanbanBoard(
                id="board-1",
                owner_node_id="method-1",
                cards=[
                    ExperimentCard(
                        id="card-1",
                        board_id="board-1",
                        column_id="running",
                        title="Experiment",
                    )
                ],
            )
        ],
    )


def test_parse_report_uses_verdict_anchor_and_normalizes_questions() -> None:
    claim = report_ingest.parse_run_report(_report())
    questions = report_ingest._build_questions(claim)

    assert claim.cause_id == "cause-new"
    assert claim.method_id == "method-1"
    assert claim.card_id == "card-1"
    assert claim.verdict == "supported"
    assert questions[0].id == "rq-card-1-1"
    assert questions[0].importance == 5
    assert questions[0].certainty.value == "definite"


@pytest.mark.parametrize(
    ("text", "message"),
    (
        ("## 0. Привязка\n", "нет секции"),
        (_report(json_body="not-json"), "невалидный JSON"),
        (
            "## 5. Заявка в базу знаний\n\n"
            "```json\n{\"method_id\": \"method-1\"}\n```\n",
            "method_id/card_id",
        ),
    ),
)
def test_parse_report_rejects_invalid_contract(text: str, message: str) -> None:
    with pytest.raises(report_ingest.ReportIngestError, match=message):
        report_ingest.parse_run_report(text)


def test_dry_run_describes_changes_without_mutating_or_persisting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project()
    report_path = tmp_path / "experiment.run.md"
    report_path.write_text(_report(), encoding="utf-8")
    saved: list[Project] = []
    ensured: list[str] = []
    monkeypatch.setattr(workflow, "load_project", lambda _project_id: project)
    monkeypatch.setattr(workflow, "save_project", saved.append)
    monkeypatch.setattr(
        workflow,
        "ensure_card_report",
        lambda *_args: ensured.append("called"),
    )
    monkeypatch.setattr(workflow, "load_index", lambda _project_id: {})

    summary = report_ingest.ingest_report("demo", report_path, dry_run=True)

    cause = next(node for node in project.nodes if node.id == "cause-new")
    method = next(node for node in project.nodes if node.id == "method-1")
    card = project.boards[0].cards[0]
    assert summary["verdict"]["new"] == "supported"
    assert cause.verdict == Verdict.OPEN
    assert [question.id for question in method.research_questions] == [
        "keep-1",
        "replace-1",
    ]
    assert card.column_id == "running"
    assert saved == []
    assert ensured == []


def test_ingest_replaces_only_current_card_insights_and_saves_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project()
    report_path = tmp_path / "experiment.run.md"
    report_path.write_text(_report(), encoding="utf-8")
    saved: list[Project] = []
    monkeypatch.setattr(workflow, "load_project", lambda _project_id: project)
    monkeypatch.setattr(workflow, "save_project", saved.append)
    monkeypatch.setattr(
        workflow,
        "ensure_card_report",
        lambda *_args: tmp_path / "experiment.md",
    )
    monkeypatch.setattr(
        workflow, "load_index", lambda _project_id: {"card-1": "experiment.md"}
    )

    summary = report_ingest.ingest_report("demo", report_path)

    method = next(node for node in project.nodes if node.id == "method-1")
    assert [question.id for question in method.research_questions] == [
        "keep-1",
        "rq-card-1-1",
    ]
    assert project.boards[0].cards[0].column_id == "done"
    assert project.nodes[0].verdict == Verdict.SUPPORTED
    assert len(saved) == 1
    assert summary["knowledge_updated"] is True


def test_service_import_remains_compatible() -> None:
    assert importlib.import_module("koi.services.report_ingest") is report_ingest

"""Unit tests for method milestones.md store and API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from koi.adapters import milestones as milestones_store
from koi.core.models import ExperimentCard, KanbanBoard, Node, NodeType, Project
from koi.projects import milestones as milestone_commands


SAMPLE_MD = """# Milestones

## 12.04.26 — First critic
<!-- id: ms-aaa11111 -->

- c-22e7cca0
- c-abc12345

## 01.06.26 — Diversity
<!-- id: ms-bbb22222 -->

"""


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    reports = tmp_path / "koi-structure" / "reports"
    reports.mkdir(parents=True)

    def fake_reports_dir(project_id: str) -> Path:
        reports.mkdir(parents=True, exist_ok=True)
        return reports

    monkeypatch.setattr(milestones_store, "reports_dir", fake_reports_dir)

    return Project(
        id="demo",
        title="Demo",
        nodes=[
            Node(
                id="m-method",
                project_id="demo",
                node_type=NodeType.METHOD,
                title="Fine-tuning cycle",
            )
        ],
        boards=[
            KanbanBoard(
                id="board-m-method",
                owner_node_id="m-method",
                cards=[
                    ExperimentCard(
                        id="c-22e7cca0",
                        board_id="board-m-method",
                        column_id="done",
                        title="Critic simplicity",
                    )
                ],
            )
        ],
    )


def test_parse_and_format_roundtrip() -> None:
    milestones = milestones_store.parse_milestones_md(SAMPLE_MD)
    assert len(milestones) == 2
    assert milestones[0].id == "ms-aaa11111"
    assert milestones[0].date == "12.04.26"
    assert milestones[0].title == "First critic"
    assert milestones[0].card_ids == ["c-22e7cca0", "c-abc12345"]
    assert milestones[1].card_ids == []

    text = milestones_store.format_milestones_md(milestones)
    again = milestones_store.parse_milestones_md(text)
    assert again[0].id == "ms-aaa11111"
    assert again[0].card_ids == ["c-22e7cca0", "c-abc12345"]
    assert again[1].title == "Diversity"


def test_load_create_save(project: Project) -> None:
    exists, items, rel = milestones_store.load_milestones(project, "m-method")
    assert exists is False
    assert items == []
    assert rel.endswith("milestones.md")

    created, _ = milestones_store.create_milestones_file(project, "m-method")
    assert created == []
    assert milestones_store.milestones_path(project, "m-method").is_file()

    payload = [
        {
            "id": "ms-one",
            "date": "12.04.26",
            "title": "Alpha",
            "card_ids": ["c-22e7cca0"],
        }
    ]
    milestones_store.save_milestones(
        project, "m-method", milestones_store.milestones_from_payload(payload)
    )
    exists2, loaded, _ = milestones_store.load_milestones(project, "m-method")
    assert exists2 is True
    assert loaded[0].card_ids == ["c-22e7cca0"]


def test_commands_and_http(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        milestone_commands.repository,
        "load_project",
        lambda project_id, *, sync_reports=False: project if project_id == "demo" else None,
    )
    monkeypatch.setattr(milestone_commands, "_enqueue_sync", lambda *a, **k: None)

    empty = milestone_commands.get_milestones("demo", "m-method")
    assert empty["exists"] is False

    created = milestone_commands.create_milestones("demo", "m-method")
    assert created["exists"] is True
    assert created["milestones"] == []

    saved = milestone_commands.save_milestones(
        "demo",
        "m-method",
        [{"date": "07.08.26", "title": "Ship UI", "card_ids": ["c-22e7cca0"]}],
    )
    assert saved["exists"] is True
    assert saved["milestones"][0]["title"] == "Ship UI"
    assert saved["relative_path"].startswith("reports/")

    client = TestClient(app)
    with patch("api.routers.milestones.get_project", return_value=project), patch(
        "koi.projects.milestones.repository.load_project",
        lambda project_id, *, sync_reports=False: project if project_id == "demo" else None,
    ):
        res = client.get("/projects/demo/nodes/m-method/milestones")
        assert res.status_code == 200
        body = res.json()
        assert body["exists"] is True
        assert body["milestones"][0]["title"] == "Ship UI"

        res2 = client.put(
            "/projects/demo/nodes/m-method/milestones",
            json={
                "milestones": [
                    {
                        "id": "ms-keep",
                        "date": "08.08.26",
                        "title": "Next",
                        "card_ids": [],
                    }
                ]
            },
        )
        assert res2.status_code == 200
        assert res2.json()["milestones"][0]["id"] == "ms-keep"

def test_sorts_by_date_not_insertion_order() -> None:
    md = """# Milestones

## 01.06.26 — Later
<!-- id: ms-later -->

## 12.04.26 — Earlier
<!-- id: ms-earlier -->

- c-22e7cca0

## 20.05.26 — Middle
<!-- id: ms-mid -->

"""
    items = milestones_store.parse_milestones_md(md)
    assert [m.id for m in items] == ["ms-earlier", "ms-mid", "ms-later"]

    unordered = milestones_store.milestones_from_payload(
        [
            {"id": "ms-b", "date": "10.08.26", "title": "B", "card_ids": []},
            {"id": "ms-a", "date": "01.08.26", "title": "A", "card_ids": []},
            {"id": "ms-x", "date": "not-a-date", "title": "X", "card_ids": []},
        ]
    )
    assert [m.id for m in unordered] == ["ms-a", "ms-b", "ms-x"]

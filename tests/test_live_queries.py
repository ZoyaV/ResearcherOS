"""Unit and HTTP contract tests for project live queries."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from koi.projects import live as live_queries
from koi.core.models import ExperimentCard, KanbanBoard, Project


@pytest.fixture
def project() -> Project:
    return Project(
        id="demo",
        title="Demo",
        boards=[
            KanbanBoard(
                id="board-method",
                owner_node_id="method",
                cards=[
                    ExperimentCard(
                        id="card-a",
                        board_id="board-method",
                        column_id="running",
                        title="Experiment",
                        description="live_log: runs/train.log",
                    )
                ],
            )
        ],
    )


def test_live_queries_coordinate_project_services(monkeypatch, project: Project) -> None:
    calls: dict[str, list] = {"activity": [], "monitor": [], "hints": [], "snapshot": []}
    monkeypatch.setattr(
        live_queries.repository,
        "load_project",
        lambda project_id, *, sync_reports=False: project if project_id == "demo" else None,
    )
    monkeypatch.setattr(
        live_queries.discoveries,
        "running_kanban_activity",
        lambda project_id: calls["activity"].append(project_id) or [{"card_id": "card-a"}],
    )
    monkeypatch.setattr(
        live_queries.live_artifacts,
        "live_monitor_cards",
        lambda project_id, loaded: calls["monitor"].append((project_id, loaded))
        or [{"card_id": "card-a"}],
    )
    monkeypatch.setattr(
        live_queries.live_artifacts,
        "merge_live_hints",
        lambda *args: calls["hints"].append(args) or {"live_log": "runs/train.log"},
    )
    monkeypatch.setattr(
        live_queries.live_artifacts,
        "live_snapshot",
        lambda *args, **kwargs: calls["snapshot"].append((args, kwargs))
        or {"active": True},
    )

    assert live_queries.running_activity("demo") == [{"card_id": "card-a"}]
    assert live_queries.live_monitor("demo") == [{"card_id": "card-a"}]
    assert live_queries.card_snapshot(
        "demo", "board-method", "card-a", tail_lines=25
    ) == {
        "ok": True,
        "card_id": "card-a",
        "column_id": "running",
        "title": "Experiment",
        "active": True,
    }
    assert calls["activity"] == ["demo"]
    assert calls["monitor"] == [("demo", project)]
    assert calls["snapshot"][0][1]["tail_lines"] == 25
    assert calls["snapshot"][0][1]["column_id"] == "running"


def test_resolve_live_file_requires_existing_file(
    monkeypatch,
    project: Project,
    tmp_path: Path,
) -> None:
    target = tmp_path / "train.log"
    target.write_text("running", encoding="utf-8")
    monkeypatch.setattr(
        live_queries.repository,
        "load_project",
        lambda project_id, *, sync_reports=False: project,
    )
    monkeypatch.setattr(
        live_queries.live_artifacts,
        "resolve_project_path",
        lambda project_id, path: target,
    )

    assert live_queries.resolve_live_file("demo", "runs/train.log") == target
    target.unlink()
    with pytest.raises(FileNotFoundError, match="File not found"):
        live_queries.resolve_live_file("demo", "runs/train.log")


def test_live_routes_delegate_to_application(tmp_path: Path) -> None:
    target = tmp_path / "train.log"
    target.write_text("running", encoding="utf-8")
    client = TestClient(app)
    with patch(
        "api.routers.projects.live_queries.running_activity",
        return_value=[{"card_id": "card-a"}],
    ), patch(
        "api.routers.projects.live_queries.live_monitor",
        return_value=[{"card_id": "card-a"}],
    ), patch(
        "api.routers.projects.live_queries.card_snapshot",
        return_value={"ok": True, "card_id": "card-a"},
    ) as card_snapshot, patch(
        "api.routers.projects.live_queries.resolve_live_file",
        return_value=target,
    ):
        activity = client.get("/projects/demo/kanban/running-activity")
        monitor = client.get("/projects/demo/kanban/live-monitor")
        snapshot = client.get(
            "/projects/demo/boards/board-method/cards/card-a/live?tail_lines=25"
        )
        file_response = client.get(
            "/projects/demo/live/file?path=runs%2Ftrain.log"
        )

    assert activity.json() == {"ok": True, "items": [{"card_id": "card-a"}]}
    assert monitor.json() == {"ok": True, "items": [{"card_id": "card-a"}]}
    assert snapshot.json() == {"ok": True, "card_id": "card-a"}
    assert file_response.content == b"running"
    card_snapshot.assert_called_once_with(
        "demo", "board-method", "card-a", tail_lines=25
    )

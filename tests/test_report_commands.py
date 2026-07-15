"""Unit and HTTP contract tests for card report use cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from koi.projects import reports as report_commands
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
                        column_id="backlog",
                        title="Experiment",
                    )
                ],
            )
        ],
    )


@pytest.fixture
def report_context(monkeypatch, project: Project) -> dict[str, list]:
    calls: dict[str, list] = {
        "read": [],
        "indexed": [],
        "write": [],
        "path": [],
        "save_asset": [],
        "resolve_asset": [],
        "sync": [],
    }
    monkeypatch.setattr(
        report_commands.repository,
        "load_project",
        lambda project_id, *, sync_reports=False: project if project_id == "demo" else None,
    )
    monkeypatch.setattr(
        report_commands.card_reports,
        "read_report",
        lambda *args: calls["read"].append(args) or {"content": "report"},
    )
    monkeypatch.setattr(
        report_commands.card_reports,
        "read_report_indexed",
        lambda *args: calls["indexed"].append(args) or {"content": "orphan"},
    )
    monkeypatch.setattr(
        report_commands.card_reports,
        "write_report",
        lambda *args: calls["write"].append(args) or {"content": args[-1]},
    )
    monkeypatch.setattr(
        report_commands.card_reports,
        "report_path_info",
        lambda *args: calls["path"].append(args) or {"relative_path": "reports/a.md"},
    )
    monkeypatch.setattr(
        report_commands.card_reports,
        "save_report_asset",
        lambda *args: calls["save_asset"].append(args) or {"filename": "chart.png"},
    )
    monkeypatch.setattr(
        report_commands.card_reports,
        "resolve_report_asset_path",
        lambda *args: calls["resolve_asset"].append(args) or Path("/tmp/chart.png"),
    )
    monkeypatch.setattr(
        report_commands,
        "_enqueue_sync",
        lambda *args: calls["sync"].append(args),
    )
    return calls


def test_report_queries_preserve_card_and_indexed_fallbacks(
    report_context: dict[str, list],
) -> None:
    assert report_commands.read_card_report(
        "demo", "board-method", "card-a"
    ) == {"content": "report"}
    assert report_commands.read_card_report(
        "demo", "board-method", "orphan-card"
    ) == {"content": "orphan"}

    assert report_context["read"][0][1:] == (
        "board-method",
        "card-a",
        "Experiment",
    )
    assert report_context["indexed"] == [("demo", "orphan-card")]


def test_report_mutations_and_assets_use_card_context(
    report_context: dict[str, list],
) -> None:
    assert report_commands.write_card_report(
        "demo", "board-method", "card-a", "updated"
    ) == {"content": "updated"}
    assert report_commands.card_report_path(
        "demo", "board-method", "card-a"
    ) == {"relative_path": "reports/a.md"}
    assert report_commands.store_report_asset(
        "demo", "board-method", "card-a", b"png", "image/png"
    ) == {"filename": "chart.png"}
    assert report_commands.report_asset_path(
        "demo", "board-method", "card-a", "chart.png"
    ) == Path("/tmp/chart.png")

    assert report_context["sync"] == [
        ("demo", "report_saved", "отчёт карточки Experiment")
    ]
    assert report_context["save_asset"][0][3:] == (
        "Experiment",
        b"png",
        "image/png",
    )
    assert report_context["resolve_asset"][0][3:] == (
        "Experiment",
        "chart.png",
    )


def test_report_routes_delegate_to_application(tmp_path: Path) -> None:
    asset = tmp_path / "chart.png"
    asset.write_bytes(b"image")
    client = TestClient(app)

    with patch(
        "api.routers.projects.report_commands.read_card_report",
        return_value={"content": "report"},
    ) as read_report, patch(
        "api.routers.projects.report_commands.write_card_report",
        return_value={"content": "updated"},
    ) as write_report, patch(
        "api.routers.projects.report_commands.store_report_asset",
        return_value={"filename": "chart.png"},
    ) as save_asset, patch(
        "api.routers.projects.report_commands.report_asset_path",
        return_value=asset,
    ), patch(
        "api.routers.projects.report_commands.ensure_report_card",
    ):
        get_response = client.get(
            "/projects/demo/boards/board-method/cards/card-a/report"
        )
        put_response = client.put(
            "/projects/demo/boards/board-method/cards/card-a/report",
            json={"content": "updated"},
        )
        upload_response = client.post(
            "/projects/demo/boards/board-method/cards/card-a/report/assets",
            files={"file": ("chart.png", b"png", "image/png")},
        )
        asset_response = client.get(
            "/projects/demo/boards/board-method/cards/card-a/report/assets/chart.png"
        )

    assert get_response.json() == {"content": "report"}
    assert put_response.json() == {"content": "updated"}
    assert upload_response.json() == {"filename": "chart.png"}
    assert asset_response.content == b"image"
    read_report.assert_called_once_with("demo", "board-method", "card-a")
    write_report.assert_called_once_with("demo", "board-method", "card-a", "updated")
    assert save_asset.call_args.args == (
        "demo",
        "board-method",
        "card-a",
        b"png",
        "image/png",
    )


def test_report_upload_checks_card_before_empty_body() -> None:
    client = TestClient(app)
    with patch(
        "api.routers.projects.report_commands.ensure_report_card",
        side_effect=report_commands.EntityNotFoundError("Card not found"),
    ):
        response = client.post(
            "/projects/demo/boards/board-method/cards/missing/report/assets",
            files={"file": ("empty.png", b"", "image/png")},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Card not found"

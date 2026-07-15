"""HTTP contract tests for routes backed by project application commands."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from koi.application import project_commands
from koi.core.models import KanbanBoard, Project


def test_create_card_route_maps_request_to_application_command() -> None:
    project = Project(
        id="demo",
        title="Demo",
        boards=[KanbanBoard(id="board-method", owner_node_id="method")],
    )
    client = TestClient(app)

    with patch(
        "api.routers.projects.project_commands.create_card",
        return_value=project,
    ) as create_card:
        response = client.post(
            "/projects/demo/boards/board-method/cards",
            json={
                "column_id": "backlog",
                "title": "Experiment",
                "tags": ["baseline"],
                "depends_on": ["card-a"],
            },
        )

    assert response.status_code == 200
    command = create_card.call_args.args[2]
    assert command == project_commands.CreateCardCommand(
        column_id="backlog",
        title="Experiment",
        tags=("baseline",),
        depends_on=("card-a",),
    )


def test_update_card_route_maps_domain_validation_to_http_400() -> None:
    client = TestClient(app)
    with patch(
        "api.routers.projects.project_commands.update_card",
        side_effect=ValueError("depends_on would create a cycle"),
    ):
        response = client.patch(
            "/projects/demo/boards/board-method/cards/card-a",
            json={"depends_on": ["card-b"]},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "depends_on would create a cycle"


def test_delete_node_route_maps_application_not_found_to_http_404() -> None:
    client = TestClient(app)
    with patch(
        "api.routers.projects.project_commands.delete_node",
        side_effect=project_commands.EntityNotFoundError("Node not found"),
    ):
        response = client.delete("/projects/demo/nodes/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Node not found"


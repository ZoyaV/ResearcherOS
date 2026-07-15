"""HTTP contract tests for routes backed by project application commands."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from koi.projects import commands as project_commands
from koi.core.models import KanbanBoard, Project


def test_create_project_route_maps_request_to_application_command() -> None:
    project = Project(id="demo", title="Demo")
    client = TestClient(app)

    with patch(
        "api.routers.projects.project_commands.create_project",
        return_value=project,
    ) as create_project:
        response = client.post(
            "/projects",
            json={
                "title": "Demo",
                "description": "Description",
                "tag": "demo",
                "program_title": "Embodied AI",
            },
        )

    assert response.status_code == 200
    assert create_project.call_args.args[0] == project_commands.CreateProjectCommand(
        title="Demo",
        project_id="demo",
        description="Description",
        program_title="Embodied AI",
    )


def test_create_project_route_maps_application_validation_to_http_400() -> None:
    client = TestClient(app)
    with patch(
        "api.routers.projects.project_commands.create_project",
        side_effect=ValueError("Project already exists: demo"),
    ):
        response = client.post(
            "/projects",
            json={"title": "Demo", "tag": "demo"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Project already exists: demo"


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


def test_replace_project_route_delegates_snapshot_to_application_command() -> None:
    project = Project(id="demo", title="Replaced")
    payload = {
        "title": "Replaced",
        "description": "Snapshot from UI",
        "nodes": [],
        "boards": {},
    }
    client = TestClient(app)

    with patch(
        "api.routers.projects.project_commands.replace_project",
        return_value=project,
    ) as replace_project:
        response = client.put("/projects/demo", json=payload)

    assert response.status_code == 200
    replace_project.assert_called_once_with("demo", payload)
    assert response.json()["id"] == "demo"
    assert response.json()["title"] == "Replaced"


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


def test_dag_suggest_route_delegates_to_application_command() -> None:
    project = Project(id="demo", title="Demo")
    suggestions = [
        {
            "from_card_id": "card-a",
            "to_card_id": "card-b",
            "confidence": 0.8,
        }
    ]
    client = TestClient(app)
    with patch(
        "api.routers.projects.project_commands.suggest_board_dependencies",
        return_value=project_commands.DagSuggestionResult(
            project=project,
            suggestions=suggestions,
            applied=1,
        ),
    ) as suggest:
        response = client.post(
            "/projects/demo/boards/board-method/dag/suggest",
            json={"apply": True},
        )

    assert response.status_code == 200
    suggest.assert_called_once_with("demo", "board-method", apply=True)
    assert response.json()["suggestions"] == suggestions
    assert response.json()["applied"] == 1
    assert response.json()["project"]["id"] == "demo"


def test_dag_suggest_preview_preserves_minimal_response() -> None:
    project = Project(id="demo", title="Demo")
    suggestions = [{"from_card_id": "card-a", "to_card_id": "card-b"}]
    client = TestClient(app)
    with patch(
        "api.routers.projects.project_commands.suggest_board_dependencies",
        return_value=project_commands.DagSuggestionResult(
            project=project,
            suggestions=suggestions,
        ),
    ):
        response = client.post(
            "/projects/demo/boards/board-method/dag/suggest",
            json={"apply": False},
        )

    assert response.status_code == 200
    assert response.json() == {"suggestions": suggestions}


def test_delete_node_route_maps_application_not_found_to_http_404() -> None:
    client = TestClient(app)
    with patch(
        "api.routers.projects.project_commands.delete_node",
        side_effect=project_commands.EntityNotFoundError("Node not found"),
    ):
        response = client.delete("/projects/demo/nodes/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Node not found"

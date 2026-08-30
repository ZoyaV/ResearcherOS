"""Tests for composite hypothesis tree merge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from koi.adapters import project_mount as pm
from koi.adapters.workspace import reset_workspace_cache
from koi.core.models import Node, NodeType, Project
from koi.projects.composites import (
    build_composite,
    composite_to_client,
    load_composite,
    members_for_composite,
)


def _write_project(
    root: Path,
    folder: str,
    project_id: str,
    *,
    composite_id: str | None = None,
    programs: list[str] | None = None,
    body: str,
) -> None:
    repo = root / folder
    koi = repo / "koi-structure"
    koi.mkdir(parents=True)
    meta_lines = [
        "---",
        f"id: {project_id}",
        f"title: {project_id}",
    ]
    if composite_id:
        meta_lines.append(f"composite_id: {composite_id}")
    if programs:
        meta_lines.append("programs:")
        for p in programs:
            meta_lines.append(f"  - {p}")
    meta_lines.append("---")
    meta_lines.append("")
    meta_lines.append(body)
    (koi / "project.md").write_text("\n".join(meta_lines) + "\n", encoding="utf-8")
    (koi / "research.json").write_text(
        json.dumps({"version": 1, "questions": []}) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def composite_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = tmp_path / "ReseachOS"
    engine.mkdir()

    shared = """# problem: p-shared

Shared problem

## cause: c-shared

Shared cause
"""
    _write_project(
        tmp_path,
        "repo_a",
        "repo-a",
        composite_id="test-composite",
        programs=["prog-a"],
        body=shared
        + """
### remediation: r-a

Branch A

#### method: m-a

Method A

<!-- koi:kanban board-a -->
| backlog | running | done | successful |
| --- | --- | --- | --- |
| Card A <!-- id:ca --> | | | |
""",
    )
    _write_project(
        tmp_path,
        "repo_b",
        "repo-b",
        composite_id="test-composite",
        programs=["prog-a"],
        body=shared
        + """
### remediation: r-b

Branch B

#### method: m-b

Method B
""",
    )

    monkeypatch.setattr(pm, "ENGINE_ROOT", engine)
    monkeypatch.setenv("KOI_SCAN_ROOTS", str(tmp_path))
    reset_workspace_cache()
    pm.rescan_projects()
    yield
    reset_workspace_cache()


def test_members_for_composite(composite_layout: None):
    assert members_for_composite("test-composite") == ["repo-a", "repo-b"]


def test_load_composite_merges_branches(composite_layout: None):
    composite = load_composite("test-composite")
    assert composite is not None
    assert composite.composite_id == "test-composite"
    assert len(composite.members) == 2

    node_ids = {n.id for n in composite.project.nodes}
    assert "p-shared" in node_ids
    assert "c-shared" in node_ids
    assert "r-a" in node_ids
    assert "r-b" in node_ids
    assert "m-a" in node_ids
    assert "m-b" in node_ids

    board_ids = {b.id for b in composite.project.boards}
    assert "board-a" in board_ids


def test_load_composite_single_member_returns_none(composite_layout: None, tmp_path: Path):
    (tmp_path / "repo_b" / "koi-structure" / "project.md").unlink()
    pm.rescan_projects()
    assert load_composite("test-composite") is None


def test_composite_serialization_exposes_conflicts_and_source_project() -> None:
    first = Project(
        id="repo-a",
        title="A",
        nodes=[
            Node(
                id="problem-shared",
                project_id="repo-a",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="Shared problem",
            )
        ],
    )
    second = Project(
        id="repo-b",
        title="B",
        nodes=[
            Node(
                id="problem-shared",
                project_id="repo-b",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="Different title",
            )
        ],
    )

    composite = build_composite(
        "shared",
        [(first.id, first), (second.id, second)],
    )
    assert composite is not None

    payload = composite_to_client(composite)

    assert payload["is_composite"] is True
    assert payload["members"] == [
        {"project_id": "repo-a", "title": "A"},
        {"project_id": "repo-b", "title": "B"},
    ]
    assert payload["conflicts"][0]["field"] == "title"
    assert payload["nodes"][0]["source_project_id"] == "repo-a"


def test_merge_collapses_same_title_different_ids() -> None:
    """Independently created shared ancestors (same titles, different ids) become one vertex."""
    first = Project(
        id="repo-a",
        title="A",
        nodes=[
            Node(
                id="p-a",
                project_id="repo-a",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="Training LLMs",
            ),
            Node(
                id="c-a",
                project_id="repo-a",
                parent_id="p-a",
                node_type=NodeType.CAUSE,
                title="Poor environment exploration",
            ),
            Node(
                id="r-a",
                project_id="repo-a",
                parent_id="c-a",
                node_type=NodeType.REMEDIATION,
                title="Branch A",
            ),
        ],
    )
    second = Project(
        id="repo-b",
        title="B",
        nodes=[
            Node(
                id="p-b",
                project_id="repo-b",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="Training LLMs",  # same title, different id
            ),
            Node(
                id="c-b",
                project_id="repo-b",
                parent_id="p-b",
                node_type=NodeType.CAUSE,
                title="  poor environment exploration  ",  # whitespace/case variant
            ),
            Node(
                id="r-b",
                project_id="repo-b",
                parent_id="c-b",
                node_type=NodeType.REMEDIATION,
                title="Branch B",
            ),
        ],
    )

    composite = build_composite("drift", [(first.id, first), (second.id, second)])
    assert composite is not None

    nodes = {n.id: n for n in composite.project.nodes}
    assert set(nodes) == {"p-a", "c-a", "r-a", "r-b"}
    assert "p-b" not in nodes
    assert "c-b" not in nodes
    assert nodes["r-b"].parent_id == "c-a"
    assert nodes["r-a"].parent_id == "c-a"
    assert nodes["c-a"].parent_id == "p-a"


def test_merge_remaps_board_owner_onto_canonical_method() -> None:
    from koi.core.models import DEFAULT_KANBAN_COLUMNS, KanbanBoard

    first = Project(
        id="repo-a",
        title="A",
        nodes=[
            Node(
                id="p-a",
                project_id="repo-a",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="P",
            ),
            Node(
                id="c-a",
                project_id="repo-a",
                parent_id="p-a",
                node_type=NodeType.CAUSE,
                title="C",
            ),
            Node(
                id="r-a",
                project_id="repo-a",
                parent_id="c-a",
                node_type=NodeType.REMEDIATION,
                title="R",
            ),
            Node(
                id="m-a",
                project_id="repo-a",
                parent_id="r-a",
                node_type=NodeType.METHOD,
                title="Shared method",
            ),
        ],
        boards=[
            KanbanBoard(
                id="board-a",
                owner_node_id="m-a",
                columns=list(DEFAULT_KANBAN_COLUMNS),
            )
        ],
    )
    second = Project(
        id="repo-b",
        title="B",
        nodes=[
            Node(
                id="p-b",
                project_id="repo-b",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="P",
            ),
            Node(
                id="c-b",
                project_id="repo-b",
                parent_id="p-b",
                node_type=NodeType.CAUSE,
                title="C",
            ),
            Node(
                id="r-b",
                project_id="repo-b",
                parent_id="c-b",
                node_type=NodeType.REMEDIATION,
                title="R",
            ),
            Node(
                id="m-b",
                project_id="repo-b",
                parent_id="r-b",
                node_type=NodeType.METHOD,
                title="Shared method",
            ),
        ],
        boards=[
            KanbanBoard(
                id="board-b",
                owner_node_id="m-b",
                columns=list(DEFAULT_KANBAN_COLUMNS),
            )
        ],
    )

    composite = build_composite("boards", [(first.id, first), (second.id, second)])
    assert composite is not None
    assert {n.id for n in composite.project.nodes} == {"p-a", "c-a", "r-a", "m-a"}
    boards = {b.id: b for b in composite.project.boards}
    assert boards["board-a"].owner_node_id == "m-a"
    assert boards["board-b"].owner_node_id == "m-a"
    payload = composite_to_client(composite)
    assert payload["boards"]["board-b"]["source_project_id"] == "repo-b"


def test_same_project_keeps_same_title_siblings() -> None:
    project = Project(
        id="repo-a",
        title="A",
        nodes=[
            Node(
                id="p1",
                project_id="repo-a",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="P",
            ),
            Node(
                id="c1",
                project_id="repo-a",
                parent_id="p1",
                node_type=NodeType.CAUSE,
                title="Same",
            ),
            Node(
                id="c2",
                project_id="repo-a",
                parent_id="p1",
                node_type=NodeType.CAUSE,
                title="Same",
            ),
        ],
    )
    other = Project(
        id="repo-b",
        title="B",
        nodes=[
            Node(
                id="p-b",
                project_id="repo-b",
                parent_id=None,
                node_type=NodeType.PROBLEM,
                title="P",
            ),
            Node(
                id="c-b",
                project_id="repo-b",
                parent_id="p-b",
                node_type=NodeType.CAUSE,
                title="Other",
            ),
        ],
    )
    composite = build_composite("sibs", [(project.id, project), (other.id, other)])
    assert composite is not None
    cause_ids = [
        n.id for n in composite.project.nodes if n.node_type == NodeType.CAUSE
    ]
    assert set(cause_ids) == {"c1", "c2", "c-b"}

"""Tests for composite hypothesis tree merge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from koi.adapters import project_mount as pm
from koi.adapters.workspace import reset_workspace_cache
from koi.services.composite import load_composite, members_for_composite


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

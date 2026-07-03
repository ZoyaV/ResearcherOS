"""Tests for laboratory / program layer (discovered projects)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from koi.adapters import project_mount as pm
from koi.adapters.workspace import reset_workspace_cache
from koi.services.programs import (
    grouped_projects,
    list_programs,
    load_laboratory,
    program_summary,
    programs_for_project,
)


@pytest.fixture
def program_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = tmp_path / "ReseachOS"
    engine.mkdir()

    def write_project(folder: str, project_id: str, programs: list[str]) -> None:
        repo = tmp_path / folder
        koi = repo / "koi-structure"
        koi.mkdir(parents=True)
        prog_yaml = "\n".join(f"  - {p}" for p in programs)
        (koi / "project.md").write_text(
            f"---\nid: {project_id}\ntitle: {project_id}\nprograms:\n{prog_yaml}\n---\n\n"
            f"# problem: p\n\n{project_id}\n",
            encoding="utf-8",
        )
        (koi / "research.json").write_text(
            json.dumps({"version": 1, "questions": []}) + "\n",
            encoding="utf-8",
        )

    write_project("proj_a", "proj-a", ["embodied-ai"])
    write_project("proj_b", "proj-b", ["embodied-ai", "demos"])

    monkeypatch.setattr(pm, "ENGINE_ROOT", engine)
    monkeypatch.setenv("KOI_SCAN_ROOTS", str(tmp_path))
    reset_workspace_cache()
    pm.rescan_projects()
    yield
    reset_workspace_cache()


def test_laboratory_loads(program_layout: None):
    lab = load_laboratory()
    assert lab["id"] == "discovered"
    assert "embodied-ai" in lab["programs"]


def test_programs_list_and_membership(program_layout: None):
    programs = list_programs()
    ids = {p["id"] for p in programs}
    assert "embodied-ai" in ids
    assert "demos" in ids
    assert "embodied-ai" in programs_for_project("proj-a")


def test_program_summary_has_totals(program_layout: None):
    summary = program_summary("embodied-ai")
    assert summary is not None
    assert summary["totals"]["projects"] == 2


def test_grouped_projects(program_layout: None):
    data = grouped_projects()
    assert data["laboratory"]["title"] == "Laboratory"
    assert any(g["id"] == "embodied-ai" for g in data["groups"])
    assigned = {p["id"] for g in data["groups"] for p in g["projects"]}
    assert "proj-a" in assigned
    assert "proj-b" in assigned
    assert "composites" in data

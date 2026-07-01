"""Tests for project discovery via koi-structure/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from koi.adapters import project_mount as pm
from koi.adapters.workspace import reset_workspace_cache


@pytest.fixture
def discovery_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = tmp_path / "ReseachOS"
    engine.mkdir()
    repo = tmp_path / "sample_project"
    koi = repo / "koi-structure"
    koi.mkdir(parents=True)
    (repo / "projectcode").mkdir()
    (koi / "project.md").write_text(
        "---\nid: sample-project\ntitle: Sample\nprograms:\n  - test-program\ncode_root: ../projectcode\n---\n\n# problem: p\n\nSample\n",
        encoding="utf-8",
    )
    (koi / "research.json").write_text(
        json.dumps({"version": 1, "questions": []}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pm, "ENGINE_ROOT", engine)
    monkeypatch.setenv("KOI_SCAN_ROOTS", str(tmp_path))
    reset_workspace_cache()
    pm.rescan_projects()
    yield tmp_path
    reset_workspace_cache()


def test_discover_projects(discovery_layout: Path):
    mounts = pm.discover_projects()
    assert len(mounts) == 1
    mount = mounts[0]
    assert mount.project_id == "sample-project"
    assert mount.repo_root.name == "sample_project"
    assert mount.koi_root.name == "koi-structure"
    assert mount.programs == ("test-program",)
    assert mount.code_root.name == "projectcode"


def test_get_mount(discovery_layout: Path):
    mount = pm.get_mount("sample-project")
    assert mount is not None
    assert mount.koi_root.joinpath("project.md").is_file()


def test_create_project_with_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = tmp_path / "ReseachOS"
    engine.mkdir()
    monkeypatch.setattr(pm, "ENGINE_ROOT", engine)
    monkeypatch.setenv("KOI_SCAN_ROOTS", str(tmp_path))
    reset_workspace_cache()
    pm.rescan_projects()

    from koi.adapters.repository import create_project

    project = create_project(
        "With Program",
        project_id="with-program",
        programs=["embodied-ai"],
    )
    assert project.id == "with-program"
    md = (tmp_path / "with_program" / "koi-structure" / "project.md").read_text(encoding="utf-8")
    assert "embodied-ai" in md
    assert "programs:" in md
    reset_workspace_cache()


def test_git_repo_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = tmp_path / "ReseachOS"
    engine.mkdir()
    for name, git_repo in [("tracked", True), ("local_only", False)]:
        repo = tmp_path / name
        koi = repo / "koi-structure"
        koi.mkdir(parents=True)
        flag = "true" if git_repo else "false"
        (koi / "project.md").write_text(
            f"---\nid: {name}\ntitle: {name}\ngit_repo: {flag}\n---\n\n# problem: p\n\n{name}\n",
            encoding="utf-8",
        )
        if git_repo:
            (repo / ".git").mkdir()
    monkeypatch.setattr(pm, "ENGINE_ROOT", engine)
    monkeypatch.setenv("KOI_SCAN_ROOTS", str(tmp_path))
    reset_workspace_cache()
    pm.rescan_projects()

    tracked = pm.get_mount("tracked")
    local = pm.get_mount("local_only")
    assert tracked is not None and tracked.git_repo is True
    assert local is not None and local.git_repo is False

    from koi.adapters.project_sync import _repo_git_roots

    roots = _repo_git_roots()
    assert (tmp_path / "tracked") in roots
    assert (tmp_path / "local_only") not in roots
    reset_workspace_cache()


def test_create_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = tmp_path / "ReseachOS"
    engine.mkdir()
    monkeypatch.setattr(pm, "ENGINE_ROOT", engine)
    monkeypatch.setenv("KOI_SCAN_ROOTS", str(tmp_path))
    reset_workspace_cache()
    pm.rescan_projects()

    from koi.adapters.repository import create_project

    project = create_project("Brand New Problem", project_id="brand-new-problem")
    assert project.id == "brand-new-problem"
    mount = pm.get_mount("brand-new-problem")
    assert mount is not None
    assert (mount.repo_root / "koi-structure" / "project.md").is_file()
    assert (mount.repo_root / "projectcode" / "README.md").is_file()
    reset_workspace_cache()

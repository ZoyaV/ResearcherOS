"""Tests for orphan-branch koi-structure git sync."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from koi.adapters import project_mount as pm
from koi.adapters.project_sync import (
    ensure_sync_branch,
    init_sync_branches,
    pull_mount,
    push_mount,
    sync_mounts,
)
from koi.adapters.workspace import reset_workspace_cache


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_remote_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    (path / "README.md").write_text("remote\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init remote")


@pytest.fixture
def sync_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = tmp_path / "ReseachOS"
    engine.mkdir()
    remote = tmp_path / "remote.git"
    _init_remote_repo(remote)

    repo = tmp_path / "sample_project"
    koi = repo / "koi-structure"
    koi.mkdir(parents=True)
    (repo / "code").mkdir()
    (koi / "project.md").write_text(
        "---\n"
        "id: sample-project\n"
        "title: Sample\n"
        "git_repo: true\n"
        "git_sync_branch: koi/research\n"
        "---\n\n"
        "# problem: p\n\nSample\n",
        encoding="utf-8",
    )
    (koi / "research.json").write_text('{"version": 1, "questions": []}\n', encoding="utf-8")

    _git(repo, "init", "-b", "feature-code")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "code branch with koi")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-u", "origin", "feature-code")

    monkeypatch.setattr(pm, "ENGINE_ROOT", engine)
    monkeypatch.setenv("KOI_SCAN_ROOTS", str(tmp_path))
    reset_workspace_cache()
    pm.rescan_projects()
    yield tmp_path
    reset_workspace_cache()


def test_sync_mounts_discovers_git_project(sync_layout: Path):
    mounts = sync_mounts()
    assert len(mounts) == 1
    assert mounts[0].project_id == "sample-project"
    assert mounts[0].git_sync_branch == "koi/research"


def test_orphan_branch_bootstrap_and_roundtrip(sync_layout: Path):
    mount = sync_mounts()[0]
    repo = mount.repo_root

    created = ensure_sync_branch(mount, push=True)
    assert created["ok"] is True
    assert created["action"] in {"created", "exists"}

  # remove koi-structure from code branch tracking
    _git(repo, "rm", "-r", "--cached", "koi-structure")
    (repo / ".gitignore").write_text("koi-structure/\n.koi-sync-worktree/\n.koi-sync-bootstrap/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "stop tracking koi-structure on code branch")

    (mount.koi_root / "research.json").write_text(
        '{"version": 1, "questions": [{"id": "q1", "question": "Test?"}]}\n',
        encoding="utf-8",
    )
    pushed = push_mount(mount)
    assert pushed["ok"] is True
    assert pushed["action"] == "pushed"

    (mount.koi_root / "research.json").write_text(
        '{"version": 1, "questions": []}\n',
        encoding="utf-8",
    )
    pulled = pull_mount(mount)
    assert pulled["ok"] is True
    assert pulled["action"] == "pulled"
    text = (mount.koi_root / "research.json").read_text(encoding="utf-8")
    assert "q1" in text

    code_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert code_branch == "feature-code"


def test_init_sync_branches_cli_entry(sync_layout: Path):
    result = init_sync_branches(project_id="sample-project", push=True)
    assert result["ok"] is True

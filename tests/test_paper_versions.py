"""Git snapshots for a paper's main.tex."""

from __future__ import annotations

import subprocess
from pathlib import Path

from koi.paper.versions import list_paper_versions, paper_tex_at_commit


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.test", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_list_and_show_paper_versions(tmp_path: Path) -> None:
    repo = tmp_path / "papers"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "branch", "-M", "main")
    tex = repo / "koi-structure" / "paper" / "neurips" / "main.tex"
    tex.parent.mkdir(parents=True)
    tex.write_text("first\n", encoding="utf-8")
    _git(repo, "add", "koi-structure/paper/neurips/main.tex")
    _git(repo, "commit", "-qm", "Add paper")
    first = _git(repo, "rev-parse", "HEAD")
    tex.write_text("second\n", encoding="utf-8")
    _git(repo, "add", "koi-structure/paper/neurips/main.tex")
    _git(repo, "commit", "-qm", "Rewrite opening")
    second = _git(repo, "rev-parse", "HEAD")
    tex.write_text("draft\n", encoding="utf-8")

    versions = list_paper_versions("demo", tex)
    assert versions["dirty"] is True
    assert versions["head"] == second
    assert [item["sha"] for item in versions["commits"]] == [second, first]
    assert versions["commits"][0]["subject"] == "Rewrite opening"
    assert paper_tex_at_commit("demo", tex, first[:8]) == "first\n"
    assert paper_tex_at_commit("demo", tex, second) == "second\n"


def test_incoming_commits_are_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "papers"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "branch", "-M", "main")
    tex = repo / "koi-structure" / "paper" / "neurips" / "main.tex"
    tex.parent.mkdir(parents=True)
    tex.write_text("first\n", encoding="utf-8")
    _git(repo, "add", "koi-structure/paper/neurips/main.tex")
    _git(repo, "commit", "-qm", "Add paper")
    tex.write_text("remote\n", encoding="utf-8")
    _git(repo, "add", "koi-structure/paper/neurips/main.tex")
    _git(repo, "commit", "-qm", "Remote edit")
    remote = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", remote)
    _git(repo, "reset", "--hard", "HEAD~1")

    versions = list_paper_versions("demo", tex)
    assert versions["behind"] == 1
    assert versions["commits"][0]["sha"] == remote
    assert versions["commits"][0]["incoming"] is True
    assert versions["commits"][0]["subject"] == "Remote edit"

from __future__ import annotations

from pathlib import Path

import pytest

from koi.services.card_live import (
    list_metric_images,
    normalize_hint_path,
    parse_live_hints,
    parse_subtasks,
    resolve_project_path,
    tail_file,
)


def test_parse_live_hints_and_subtasks():
    text = """live_log: runs/train.log
metrics_dir: runs/plots
live_note: epoch 3 running

Подзадачи:
- [x] Sync code
- [ ] Train model
"""
    hints = parse_live_hints(text)
    assert hints["live_log"] == "runs/train.log"
    assert hints["metrics_dir"] == "runs/plots"
    assert hints["live_note"] == "epoch 3 running"
    subs = parse_subtasks(text)
    assert subs["done"] == ["Sync code"]
    assert subs["open"] == ["Train model"]


def test_resolve_and_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "proj"
    repo.mkdir()
    log = repo / "runs" / "train.log"
    log.parent.mkdir(parents=True)
    log.write_text("line1\nline2\nline3\n", encoding="utf-8")

    monkeypatch.setattr(
        "koi.services.card_live.repo_root",
        lambda _pid: repo,
    )

    resolved = resolve_project_path("proj", "runs/train.log")
    assert resolved == log.resolve()
    assert tail_file(resolved, lines=2) == "line2\nline3"


def test_list_metric_images(tmp_path: Path):
    plots = tmp_path / "plots"
    plots.mkdir()
    (plots / "a.png").write_bytes(b"x")
    (plots / "b.txt").write_text("nope", encoding="utf-8")
    images = list_metric_images(plots)
    assert len(images) == 1
    assert images[0]["name"] == "a.png"


def test_normalize_hint_path_strips_repo_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "verl-agent-craftext"
    repo.mkdir()
    monkeypatch.setattr(
        "koi.services.card_live.repo_root",
        lambda _pid: repo,
    )
    assert (
        normalize_hint_path("verl-agent-craftext", "../verl-agent-craftext/runs/plots/4b_v3")
        == "runs/plots/4b_v3"
    )


def test_resolve_rejects_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "proj"
    repo.mkdir()
    monkeypatch.setattr(
        "koi.services.card_live.repo_root",
        lambda _pid: repo,
    )
    with pytest.raises(ValueError, match="outside"):
        resolve_project_path("proj", "../../../etc/passwd")

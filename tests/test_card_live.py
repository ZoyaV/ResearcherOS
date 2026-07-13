from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from koi.services.card_live import (
    has_live_hints,
    is_live_active,
    list_metric_images,
    normalize_hint_path,
    parse_live_hints,
    parse_subtasks,
    resolve_project_path,
    tail_file,
)


def test_parse_subtasks_inline_and_multiline() -> None:
    text = "note\n- [x] Sync code\n- [ ] Train model"
    subs = parse_subtasks(text)
    assert subs["done"] == ["Sync code"]
    assert subs["open"] == ["Train model"]

    inline = "note - [x] A - [ ] B"
    subs_inline = parse_subtasks(inline)
    assert subs_inline["done"] == ["A"]
    assert subs_inline["open"] == ["B"]


def test_parse_subtasks_last_item_before_section() -> None:
    text = """## 3. Подзадачи

- [X] Done item
- [ ] Open item

## 4. Results
"""
    subs = parse_subtasks(text)
    assert subs["done"] == ["Done item"]
    assert subs["open"] == ["Open item"]


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


def test_has_live_hints():
    assert has_live_hints({"live_log": "runs/a.log"})
    assert not has_live_hints({})
    assert not has_live_hints({"live_log": "  "})


def test_is_live_active_recent_log():
    snapshot = {
        "live_note": "",
        "live_log": {
            "configured": True,
            "exists": True,
            "mtime": datetime.now(timezone.utc).isoformat(),
        },
        "metrics_dir": {"configured": False, "images": []},
    }
    assert is_live_active(snapshot)


def test_is_live_active_stale_log_with_note_only_paths():
    snapshot = {
        "live_note": "epoch 3",
        "live_log": {
            "configured": True,
            "exists": True,
            "mtime": "2020-01-01T00:00:00+00:00",
        },
        "metrics_dir": {"configured": False, "images": []},
    }
    assert not is_live_active(snapshot)


def test_is_live_active_running_with_stale_metrics():
    snapshot = {
        "live_note": "",
        "live_log": {"configured": True, "exists": True, "mtime": "2020-01-01T00:00:00+00:00"},
        "metrics_dir": {
            "configured": True,
            "exists": True,
            "images": [{"name": "sr.png", "mtime": "2020-01-01T00:00:00+00:00"}],
        },
    }
    assert is_live_active(snapshot, column_id="running")
    assert not is_live_active(snapshot, column_id="done")


def test_is_live_active_note_only():
    snapshot = {
        "live_note": "writing section 2",
        "live_log": {"configured": False},
        "metrics_dir": {"configured": False, "images": []},
    }
    assert is_live_active(snapshot)


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

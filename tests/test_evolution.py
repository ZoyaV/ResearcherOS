from __future__ import annotations

import json
from pathlib import Path

from koi.evolution.runner import launch, read_run


def test_launch_creates_headless_run_state(tmp_path: Path) -> None:
    run = launch(tmp_path, "demo-1", ["/bin/sh", "-c", "printf 'hello\\n'"])
    state = json.loads((tmp_path / "runs/evo/demo-1/state.json").read_text())

    assert run.status == "running"
    assert state["run_id"] == "demo-1"
    assert state["command"] == ["/bin/sh", "-c", "printf 'hello\\n'"]
    assert read_run(tmp_path, "demo-1").pid == run.pid


def test_run_id_cannot_escape_run_directory(tmp_path: Path) -> None:
    try:
        launch(tmp_path, "../outside", ["/bin/true"])
    except ValueError as exc:
        assert "run_id" in str(exc)
    else:
        raise AssertionError("unsafe run id was accepted")

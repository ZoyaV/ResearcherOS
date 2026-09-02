"""Small, dependency-free adapter around the Evo CLI.

ResearchOS owns the card, report and verdict. Evo owns code experiments and
their benchmark traces. This module deliberately uses the CLI boundary rather
than importing Evo internals, so the ResearchOS monitor can remain the UI.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class EvoRun:
    run_id: str
    root: Path
    status: str
    pid: int | None = None
    returncode: int | None = None
    summary: dict[str, Any] | None = None


def _run_root(root: Path, run_id: str) -> Path:
    safe = "".join(ch for ch in str(run_id) if ch.isalnum() or ch in "-_.")
    if not safe or safe != str(run_id):
        raise ValueError("run_id must contain only letters, digits, '-', '_' or '.'")
    return root / "runs" / "evo" / safe


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_run(root: Path, run_id: str) -> EvoRun:
    """Read the normalized monitor state for one run."""
    run_root = _run_root(root, run_id)
    state_path = run_root / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(state_path)
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return EvoRun(
        run_id=run_id,
        root=run_root,
        status=str(payload.get("status") or "unknown"),
        pid=payload.get("pid"),
        returncode=payload.get("returncode"),
        summary=payload.get("summary") or {},
    )


def launch(
    root: Path,
    run_id: str,
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> EvoRun:
    """Launch a headless Evo command and create its ResearchOS state record.

    The command is supplied by the card/project configuration; no shell is
    involved. A tiny watcher process is intentionally not spawned here: the
    monitor can observe the state and the launcher updates it on completion.
    """
    if not command:
        raise ValueError("command must not be empty")
    run_root = _run_root(root, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    stdout = (run_root / "stdout.log").open("ab")
    child_env = os.environ.copy()
    child_env.update({str(k): str(v) for k, v in (env or {}).items()})
    child_env.setdefault("EVO_TRACES_DIR", str(run_root / "traces"))
    child_env.setdefault("EVO_EXPERIMENT_ID", run_id)
    process = subprocess.Popen(
        [str(item) for item in command],
        cwd=str(cwd or root),
        env=child_env,
        stdout=stdout,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _write_json(
        run_root / "state.json",
        {
            "run_id": run_id,
            "status": "running",
            "pid": process.pid,
            "started_at": time.time(),
            "command": [str(item) for item in command],
            "cwd": str(cwd or root),
            "summary": {},
        },
    )
    return read_run(root, run_id)

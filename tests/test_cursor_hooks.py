"""Import-smoke checks for Cursor hooks without executing their main functions."""

import runpy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative_path",
    (
        ".cursor/hooks/koi-agent-chat-hook.py",
        ".cursor/hooks/koi-done-research-hook.py",
        ".cursor/hooks/koi-project-sync-hook.py",
    ),
)
def test_cursor_hook_imports(relative_path: str) -> None:
    namespace = runpy.run_path(str(ROOT / relative_path), run_name="cursor_hook_smoke")

    assert callable(namespace["main"])

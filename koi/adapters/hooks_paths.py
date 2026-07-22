"""Resolve ResearchOS root from a Cursor hook script path."""

from __future__ import annotations

from pathlib import Path


def koi_root_from_hook(hook_file: str | Path) -> Path:
    """Walk up from *hook_file* until the package root (``koi/agent_chat/cli.py``).

    Hooks may live under ``.cursor/hooks/`` (legacy) or
    ``agents/skills/<skill>/hooks/`` / ``agents/hooks/``.
    """
    cur = Path(hook_file).resolve().parent
    for _ in range(10):
        if (cur / "koi" / "agent_chat" / "cli.py").is_file():
            return cur
        nested = cur / "KOI"
        if (nested / "koi" / "agent_chat" / "cli.py").is_file():
            return nested
        if cur.parent == cur:
            break
        cur = cur.parent
    # Last-resort fallback for odd layouts.
    return Path(hook_file).resolve().parents[3]

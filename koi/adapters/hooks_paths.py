"""Resolve KOI root from a hook script path (workspace may be KOI or parent zverl)."""

from __future__ import annotations

from pathlib import Path


def koi_root_from_hook(hook_file: str | Path) -> Path:
    """Return KOI package root for hooks living in <workspace>/.cursor/hooks/."""
    workspace = Path(hook_file).resolve().parent.parent.parent
    if (workspace / "scripts" / "koi_agent_chat.py").is_file():
        return workspace
    nested = workspace / "KOI"
    if (nested / "scripts" / "koi_agent_chat.py").is_file():
        return nested
    return workspace

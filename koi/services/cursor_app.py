"""Detect whether Cursor IDE is running and frontmost on the local machine."""

from __future__ import annotations

import platform
import subprocess


def _run_command(args: list[str], *, timeout: float = 1.5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def cursor_is_running() -> bool:
    system = platform.system()
    if system == "Darwin":
        proc = _run_command(["pgrep", "-f", "/Applications/Cursor.app/Contents/MacOS/Cursor"])
        if proc is not None and proc.returncode == 0:
            return True
        proc = _run_command(["pgrep", "-f", "Cursor.app/Contents/MacOS/Cursor"])
        return proc is not None and proc.returncode == 0
    if system == "Windows":
        proc = _run_command(["tasklist", "/FI", "IMAGENAME eq Cursor.exe"])
        return proc is not None and "Cursor.exe" in (proc.stdout or "")
    proc = _run_command(["pgrep", "-f", "cursor"])
    return proc is not None and proc.returncode == 0


def _cursor_frontmost_via_lsappinfo() -> str | None:
    front = _run_command(["lsappinfo", "front"])
    if front is None or front.returncode != 0:
        return None
    asn = (front.stdout or "").strip().split()
    if not asn:
        return None
    info = _run_command(["lsappinfo", "info", asn[0]])
    if info is None or info.returncode != 0:
        return None
    for line in (info.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith('"') and "ASN:" in stripped:
            return stripped.split('"', 2)[1]
    return None


def cursor_frontmost_app_name() -> str | None:
    system = platform.system()
    if system == "Darwin":
        name = _cursor_frontmost_via_lsappinfo()
        if name:
            return name
        proc = _run_command(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first application process whose frontmost is true',
            ]
        )
        if proc is not None and proc.returncode == 0:
            fallback = (proc.stdout or "").strip()
            if fallback:
                return fallback
        return None
    if system == "Windows":
        return None
    proc = _run_command(["xdotool", "getactivewindow", "getwindowname"])
    if proc is None or proc.returncode != 0:
        return None
    title = (proc.stdout or "").strip()
    return title or None


def cursor_is_frontmost() -> bool:
    name = cursor_frontmost_app_name()
    if not name:
        return False
    lowered = name.casefold()
    return lowered == "cursor" or "cursor" in lowered


def cursor_is_active() -> bool:
    """True when Cursor is the frontmost application."""
    return cursor_is_frontmost()

#!/usr/bin/env python3
"""Cursor hook: git pull on session start, push/pull reminders on stop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

def _koi_root() -> Path:
    cur = Path(__file__).resolve().parent
    for _ in range(10):
        if (cur / "koi" / "agent_chat" / "cli.py").is_file():
            return cur
        nested = cur / "KOI"
        if (nested / "koi" / "agent_chat" / "cli.py").is_file():
            return nested
        if cur.parent == cur:
            break
        cur = cur.parent
    raise SystemExit(f"ResearchOS root not found from {__file__}")


KOI_ROOT = _koi_root()
if str(KOI_ROOT) not in sys.path:
    sys.path.insert(0, str(KOI_ROOT))

from koi.adapters.project_sync import git_summary  # noqa: E402
from koi.adapters.project_sync_queue import (  # noqa: E402
    list_pending_push,
    should_periodic_pull,
)
from koi.projects.sync import pull_projects  # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else "session"


def _format_session_context(summary: dict, pull_result: dict) -> str:
    lines = ["## KOI project sync", ""]

    action = pull_result.get("action")
    if action == "pulled":
        lines.append(f"**Pull:** {pull_result.get('message', 'ok')}")
    elif action == "blocked":
        lines.append(f"**Pull blocked:** {pull_result.get('message', '')}")
    elif action == "failed":
        lines.append(f"**Pull error:** {pull_result.get('message', '')}")
    elif summary.get("behind", 0):
        lines.append(f"**Remote is {summary['behind']} commits ahead** — pull required.")
    else:
        lines.append("**Pull:** up to date.")

    pending = summary.get("pending_push") or list_pending_push()
    dirty = summary.get("dirty_project_paths") or []
    if pending or dirty:
        lines.append("")
        lines.append(
            f"**Push:** queue {len(pending)}, uncommitted files in projects/: {len(dirty)}."
        )
        lines.append(
            "Use **koi-project-sync**: commit and push projects/, then complete-push --all."
        )
        for item in pending[:8]:
            lines.append(f"- `{item['project_id']}` {item['reason']}: {item['detail']}")
        if len(pending) > 8:
            lines.append(f"- … {len(pending) - 8} more")

    return "\n".join(lines)


def main() -> None:
    raw = sys.stdin.read()
    hook_input = json.loads(raw) if raw.strip() else {}

    if not (KOI_ROOT / ".git").exists():
        print("{}")
        return

    try:
        summary = git_summary()
        pull_result = pull_projects(dry_run=False)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "additional_context": (
                        "## KOI project sync\n\n"
                        f"Could not check git: {exc}. Run **koi-project-sync** manually."
                    )
                },
                ensure_ascii=False,
            )
        )
        return

    if MODE == "session":
        if hook_input.get("composer_mode") == "ask":
            print("{}")
            return
        ctx = _format_session_context(summary, pull_result)
        env = {}
        if summary.get("pending_push") or summary.get("dirty_project_paths"):
            env["KOI_SYNC_PUSH_PENDING"] = "1"
        print(json.dumps({"env": env, "additional_context": ctx}, ensure_ascii=False))
        return

    if MODE == "stop":
        if hook_input.get("status") != "completed":
            print("{}")
            return

        followups: list[str] = []
        try:
            summary = git_summary()
        except Exception:
            summary = {}

        pending = summary.get("pending_push") or []
        dirty = summary.get("dirty_project_paths") or []
        if pending or dirty:
            followups.append(
                "Project-sync queue: commit and push projects/, then complete-push --all."
            )

        if should_periodic_pull():
            followups.append("At least 30 minutes have passed; run pull (koi-project-sync).")

        if not followups:
            print("{}")
            return

        print(json.dumps({"followup_message": " ".join(followups)}, ensure_ascii=False))
        return

    print("{}")


if __name__ == "__main__":
    main()

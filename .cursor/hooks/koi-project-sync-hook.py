#!/usr/bin/env python3
"""Cursor hook: git pull on session start, push/pull reminders on stop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HOOK = Path(__file__).resolve()
_WORKSPACE = _HOOK.parent.parent.parent
KOI_ROOT = (
    _WORKSPACE
    if (_WORKSPACE / "scripts" / "koi_agent_chat.py").is_file()
    else _WORKSPACE / "KOI"
)
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
        lines.append(f"**Pull заблокирован:** {pull_result.get('message', '')}")
    elif action == "failed":
        lines.append(f"**Pull ошибка:** {pull_result.get('message', '')}")
    elif summary.get("behind", 0):
        lines.append(f"**Remote впереди на {summary['behind']} коммитов** — нужен pull.")
    else:
        lines.append("**Pull:** актуально.")

    pending = summary.get("pending_push") or list_pending_push()
    dirty = summary.get("dirty_project_paths") or []
    if pending or dirty:
        lines.append("")
        lines.append(
            f"**Push:** очередь {len(pending)}, незакоммиченных файлов в projects/: {len(dirty)}."
        )
        lines.append(
            "Скилл **koi-project-sync**: commit + push для projects/, затем complete-push --all."
        )
        for item in pending[:8]:
            lines.append(f"- `{item['project_id']}` {item['reason']}: {item['detail']}")
        if len(pending) > 8:
            lines.append(f"- … ещё {len(pending) - 8}")

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
                        f"Не удалось проверить git: {exc}. Скилл **koi-project-sync** вручную."
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
                "Очередь project-sync: commit + push projects/, затем complete-push --all."
            )

        if should_periodic_pull():
            followups.append("Прошло ≥30 мин — выполни pull (koi-project-sync).")

        if not followups:
            print("{}")
            return

        print(json.dumps({"followup_message": " ".join(followups)}, ensure_ascii=False))
        return

    print("{}")


if __name__ == "__main__":
    main()

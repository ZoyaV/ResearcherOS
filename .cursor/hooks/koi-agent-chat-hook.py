#!/usr/bin/env python3
"""Cursor hook: agent-chat queue → IDE agent (cursor_ide mode only)."""

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

from koi.agent_chat_queue import list_pending  # noqa: E402
from koi.settings_store import is_cursor_ide_agent_mode, load_env_file  # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else "session"
VENV_PY = KOI_ROOT / ".venv" / "bin" / "python"
CHAT_PY = KOI_ROOT / "scripts" / "koi_agent_chat.py"


def format_context(items: list) -> str:
    lines = [
        "## ResearchOS: вопросы из UI (agent-chat)",
        f"В очереди {len(items)} вопрос(а/ов) из панели «Спросить агента».",
        "Примени скилл **koi-agent-chat**: `context` → ответ (сначала research_database) → "
        f"`{VENV_PY if VENV_PY.is_file() else 'python3'} {CHAT_PY} answer <id>`.",
        "",
        "Очередь:",
    ]
    for item in items:
        scope = []
        if item.get("method_id"):
            scope.append(f"method={item['method_id']}")
        if item.get("node_id"):
            scope.append(f"node={item['node_id']}")
        scope_s = f" ({', '.join(scope)})" if scope else ""
        q = item["question"]
        short = f"«{q[:120]}{'…' if len(q) > 120 else ''}»"
        lines.append(f"- id={item['id']} project={item['project_id']}{scope_s}: {short}")
    return "\n".join(lines)


def main() -> None:
    raw = sys.stdin.read()
    hook_input = json.loads(raw) if raw.strip() else {}

    load_env_file()
    if not is_cursor_ide_agent_mode():
        print("{}")
        return

    try:
        items = list_pending()
    except Exception:
        items = []

    if not items:
        print("{}")
        return

    if MODE == "session":
        if hook_input.get("composer_mode") == "ask":
            print("{}")
            return
        print(
            json.dumps(
                {
                    "env": {"KOI_AGENT_CHAT_PENDING": str(len(items))},
                    "additional_context": format_context(items),
                },
                ensure_ascii=False,
            )
        )
        return

    if MODE == "stop":
        if hook_input.get("status") != "completed":
            print("{}")
            return
        first = items[0]
        py = str(VENV_PY) if VENV_PY.is_file() else "python3"
        msg = (
            f"В очереди agent-chat {len(items)} вопрос(а/ов). "
            f"Скилл **koi-agent-chat**, id={first['id']}: "
            f"`{py} {CHAT_PY} context {first['id']}` → ответ → "
            f"`answer {first['id']}` (обязательно в UI). "
            "Сначала research.json, отчёт — только при нехватке деталей."
        )
        print(json.dumps({"followup_message": msg}, ensure_ascii=False))
        return

    print("{}")


if __name__ == "__main__":
    main()

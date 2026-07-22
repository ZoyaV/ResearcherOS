#!/usr/bin/env python3
"""Cursor hook: done-research queue → IDE agent."""

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

from koi.adapters.agent_chat_queue import list_pending as list_agent_chat  # noqa: E402
from koi.adapters.done_research_queue import list_pending  # noqa: E402
from koi.adapters.settings_store import (  # noqa: E402
    is_cursor_manual_agent_mode,
    load_env_file,
)

MODE = sys.argv[1] if len(sys.argv) > 1 else "session"


def format_context(items: list) -> str:
    lines = [
        "## KOI done-research queue",
        f"В очереди {len(items)} карточ(ка/ки/ек) после переноса в done.",
        "Скилл **koi-done-research**: context → вывод (certainty + importance) → "
        "PATCH research_questions → complete.",
        "",
        "Очередь:",
    ]
    for item in items:
        lines.append(
            f"- project={item['project_id']} board={item['board_id']} "
            f"card={item['card_id']} (since {item['enqueued_at']})"
        )
    return "\n".join(lines)


def main() -> None:
    raw = sys.stdin.read()
    hook_input = json.loads(raw) if raw.strip() else {}

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
                    "env": {"KOI_DONE_RESEARCH_PENDING": str(len(items))},
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
        load_env_file()
        if is_cursor_manual_agent_mode():
            try:
                if list_agent_chat():
                    print("{}")
                    return
            except Exception:
                pass
        msg = (
            f"В очереди done-research осталось карточек: {len(items)}. "
            "Скилл koi-done-research: context → research_questions → complete."
        )
        print(json.dumps({"followup_message": msg}, ensure_ascii=False))
        return

    print("{}")


if __name__ == "__main__":
    main()

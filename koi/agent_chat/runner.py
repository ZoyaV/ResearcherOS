"""Process one agent-chat queue item: research.json auto-answer, then LLM agent.

Order: first try the free automatic answer from research.json. If the database
does not cover the question, use a local agent through koi.adapters.agent_backends
(Claude Code CLI and/or Cursor SDK; see KOI_AGENT_BACKEND). If no backend is
available, send setup instructions to the chat.
"""

from __future__ import annotations

import json
from koi.adapters.agent_backends import backend_status, run_agent
from koi.agent_chat.cli import build_context
from koi.agent_chat.auto import try_auto_answer
from koi.agent_chat.formatting import ANSWER_FORMAT_INSTRUCTIONS, no_cursor_key_warning
from koi.adapters.agent_chat_queue import find_item, list_pending, submit_answer
from koi.adapters.settings_store import is_api_agent_mode, is_cursor_manual_agent_mode, load_env_file
from koi.adapters.workspace import get_workspace

_ws = get_workspace()


def _sdk_prompt(item_id: str) -> str:
    ctx = build_context(item_id)
    return (
        "You answer a researcher's question in ResearchOS using koi-agent-chat.\n"
        "Content rules:\n"
        "1. Use research_database in JSON first (narrative, answer).\n"
        "2. Open report_path only when the database lacks details.\n"
        "3. If the database has no answer, say plainly that existing experiments do not cover the question.\n\n"
        f"{ANSWER_FORMAT_INSTRUCTIONS}\n\n"
        "Return ONLY the final answer text for the UI panel.\n\n"
        f"Context:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"
    )


def _any_backend_available() -> bool:
    status = backend_status()
    return any(
        status.get(name, {}).get("available") for name in status.get("order", [])
    )


def process_item(item_id: str) -> bool:
    """Auto-answer or LLM agent (claude/cursor). Returns True if answer saved."""
    item = find_item(item_id)
    if item is None or item.get("status") == "answered":
        return False

    auto = try_auto_answer(item["project_id"], item["question"])
    if auto:
        submit_answer(item_id, auto)
        return True

    load_env_file()  # Load UI settings from KOI/.env without overwriting existing values.
    if is_cursor_manual_agent_mode():
        return False

    if not _any_backend_available():
        submit_answer(item_id, no_cursor_key_warning(), answer_kind="warning")
        return True

    text, _backend = run_agent(_sdk_prompt(item_id), cwd=_ws.agent_cwd())
    if text:
        submit_answer(item_id, text)
        return True
    return False


def process_all_pending() -> int:
    done = 0
    for item in list(list_pending()):
        if process_item(item["id"]):
            done += 1
    return done

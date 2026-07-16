"""Derive running-card activity for Hub snapshots (no local git history)."""

from __future__ import annotations

import re
from typing import Any


def open_subtask_from_card(card: dict[str, Any]) -> str:
    for line in str(card.get("description") or "").replace("\\n", "\n").split("\n"):
        m = re.match(r"^\s*-\s*\[ \]\s*(.+)", line)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return str(card.get("title") or "").strip()


def running_activity_for_project(
    project: dict[str, Any], *, author: str
) -> list[dict[str, Any]]:
    boards = project.get("boards") or {}
    if not isinstance(boards, dict):
        return []
    who = (author or "").strip() or "коллега"
    items: list[dict[str, Any]] = []
    for board in boards.values():
        if not isinstance(board, dict):
            continue
        board_id = str(board.get("id") or "")
        for card in board.get("cards") or []:
            if not isinstance(card, dict) or card.get("column_id") != "running":
                continue
            card_id = str(card.get("id") or "")
            if not card_id:
                continue
            items.append(
                {
                    "card_id": card_id,
                    "board_id": board_id,
                    "author": who,
                    "title": str(card.get("title") or card_id),
                    "task": open_subtask_from_card(card),
                }
            )
    return items

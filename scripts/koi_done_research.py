#!/usr/bin/env python3
"""Context and queue helpers for done-card → research-question workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from koi.adapters.card_reports import read_report  # noqa: E402
from koi.adapters.done_research_queue import dequeue, list_pending  # noqa: E402
from koi.adapters.repository import load_project  # noqa: E402


def _find_card(project, board_id: str, card_id: str):
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        raise SystemExit(f"Board not found: {board_id}")
    card = next((c for c in board.cards if c.id == card_id), None)
    if card is None:
        raise SystemExit(f"Card not found: {card_id}")
    return board, card


def _method_context(project, board):
    method = next((n for n in project.nodes if n.id == board.owner_node_id), None)
    if method is None:
        raise SystemExit(f"Method node not found for board {board.id}")
    parent = (
        next((n for n in project.nodes if n.id == method.parent_id), None)
        if method.parent_id
        else None
    )
    return method, parent


def build_context(project_id: str, board_id: str, card_id: str) -> dict:
    project = load_project(project_id, sync_reports=False)
    if project is None:
        raise SystemExit(f"Project not found: {project_id}")
    board, card = _find_card(project, board_id, card_id)
    method, parent = _method_context(project, board)
    report = ""
    try:
        report = read_report(project, board_id, card_id, card.title).get("content", "")
    except Exception:
        report = ""

    return {
        "project_id": project_id,
        "project_title": project.title,
        "board_id": board_id,
        "card_id": card_id,
        "card": {
            "title": card.title,
            "description": card.description,
            "column_id": card.column_id,
        },
        "method": {
            "id": method.id,
            "title": method.title,
            "description": method.description,
            "research_questions": [
                {
                    "id": q.id,
                    "question": q.question,
                    "answer": q.answer,
                    "narrative": q.narrative,
                    "certainty": q.certainty.value,
                    "importance": q.importance,
                    "card_id": q.card_id,
                }
                for q in method.research_questions
            ],
        },
        "parent_hypothesis": (
            {
                "id": parent.id,
                "title": parent.title,
                "description": parent.description,
                "node_type": parent.node_type.value,
            }
            if parent
            else None
        ),
        "report_markdown": report.strip(),
    }


def cmd_pending(_: argparse.Namespace) -> None:
    print(json.dumps(list_pending(), ensure_ascii=False, indent=2))


def cmd_context(args: argparse.Namespace) -> None:
    ctx = build_context(args.project_id, args.board_id, args.card_id)
    print(json.dumps(ctx, ensure_ascii=False, indent=2))


def cmd_complete(args: argparse.Namespace) -> None:
    ok = dequeue(args.project_id, args.board_id, args.card_id)
    if not ok:
        raise SystemExit("Item not in queue")
    print("ok")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pending = sub.add_parser("pending", help="List queued done cards")
    p_pending.set_defaults(func=cmd_pending)

    p_ctx = sub.add_parser("context", help="JSON context for one card")
    p_ctx.add_argument("project_id")
    p_ctx.add_argument("board_id")
    p_ctx.add_argument("card_id")
    p_ctx.set_defaults(func=cmd_context)

    p_done = sub.add_parser("complete", help="Remove card from queue")
    p_done.add_argument("project_id")
    p_done.add_argument("board_id")
    p_done.add_argument("card_id")
    p_done.set_defaults(func=cmd_complete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Queue helpers for ResearchOS Related Work → Cursor agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from koi.adapters.related_work_queue import list_pending  # noqa: E402
from koi.services.related_work import (  # noqa: E402
    answer_related_work_item,
    build_related_work_context,
    claim_related_work_item,
)


def cmd_pending(_: argparse.Namespace) -> None:
    print(json.dumps(list_pending(), ensure_ascii=False, indent=2))


def cmd_context(args: argparse.Namespace) -> None:
    print(json.dumps(build_related_work_context(args.queue_id), ensure_ascii=False, indent=2))


def cmd_answer(args: argparse.Namespace) -> None:
    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    if not text or not text.strip():
        raise SystemExit("Markdown is empty")
    try:
        item = answer_related_work_item(args.queue_id, text)
    except KeyError as e:
        raise SystemExit(str(e)) from e
    print(json.dumps(item, ensure_ascii=False, indent=2))


def cmd_claim(args: argparse.Namespace) -> None:
    try:
        item = claim_related_work_item(args.queue_id)
    except KeyError as e:
        raise SystemExit(str(e)) from e
    print(json.dumps(item, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pending = sub.add_parser("pending", help="List pending Related Work jobs")
    p_pending.set_defaults(func=cmd_pending)

    p_ctx = sub.add_parser("context", help="JSON context for one queue item")
    p_ctx.add_argument("queue_id")
    p_ctx.set_defaults(func=cmd_context)

    p_answer = sub.add_parser("answer", help="Save Related Work markdown (shown in UI)")
    p_answer.add_argument("queue_id")
    p_answer.add_argument("text", nargs="?", default="")
    p_answer.add_argument("--file", "-f", help="Read markdown from file")
    p_answer.set_defaults(func=cmd_answer)

    p_claim = sub.add_parser("claim", help="Mark Related Work as accepted by agent (updates UI)")
    p_claim.add_argument("queue_id")
    p_claim.set_defaults(func=cmd_claim)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

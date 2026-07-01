#!/usr/bin/env python3
"""ResearchOS Inbox — watcher + queue status for a dedicated Cursor agent chat."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from koi.agent_chat_inbox import (  # noqa: E402
    bootstrap_prompt,
    format_pending_report,
    inbox_settings,
    pending_signature,
    pending_snapshot,
    run_watch,
)


def cmd_status(_: argparse.Namespace) -> None:
    data = inbox_settings()
    data["pending_ids"] = list(pending_signature())
    data["pending"] = pending_snapshot()
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_bootstrap(_: argparse.Namespace) -> None:
    print(bootstrap_prompt())


def cmd_pending(args: argparse.Namespace) -> None:
    if args.json:
        print(json.dumps(pending_snapshot(), ensure_ascii=False, indent=2))
    else:
        print(format_pending_report())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_watch = sub.add_parser(
        "watch",
        help="Watch agent-chat queue; print AGENT_CHAT_WAKE lines (run via koi-serve)",
    )
    p_watch.set_defaults(func=lambda _a: run_watch())

    p_pending = sub.add_parser(
        "pending",
        help="Show pending tasks from agent-chat JSON queue",
    )
    p_pending.add_argument("--json", action="store_true", help="Machine-readable JSON")
    p_pending.set_defaults(func=cmd_pending)

    p_status = sub.add_parser("status", help="JSON status for UI / diagnostics")
    p_status.set_defaults(func=cmd_status)

    p_boot = sub.add_parser(
        "bootstrap",
        help="Print first message to paste into new Cursor Inbox chat",
    )
    p_boot.set_defaults(func=cmd_bootstrap)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

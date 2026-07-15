#!/usr/bin/env python3
"""ResearchOS Literature Inbox — watcher + queue status for Related Work."""

from __future__ import annotations

import argparse
import json

from koi.related_work.inbox import (
    bootstrap_prompt,
    format_pending_report,
    literature_inbox_settings,
    pending_signature,
    pending_snapshot,
    run_watch,
)


def cmd_status(_: argparse.Namespace) -> None:
    data = literature_inbox_settings()
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
        help="Watch related-work queue; print RELATED_WORK_WAKE lines",
    )
    p_watch.set_defaults(func=lambda _a: run_watch())

    p_pending = sub.add_parser("pending", help="Show pending Related Work tasks")
    p_pending.add_argument("--json", action="store_true", help="Machine-readable JSON")
    p_pending.set_defaults(func=cmd_pending)

    p_status = sub.add_parser("status", help="JSON status for UI / diagnostics")
    p_status.set_defaults(func=cmd_status)

    p_boot = sub.add_parser(
        "bootstrap",
        help="Print first message for ResearchOS Literature Inbox chat",
    )
    p_boot.set_defaults(func=cmd_bootstrap)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

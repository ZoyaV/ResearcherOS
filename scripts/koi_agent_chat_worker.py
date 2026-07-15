#!/usr/bin/env python3
"""Background worker: answer pending agent-chat items (auto + optional Cursor SDK)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from koi.services.agent_chat_runner import process_all_pending, process_item  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process pending queue once and exit",
    )
    parser.add_argument("--id", help="Process single queue item id")
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Poll interval in seconds (daemon mode)",
    )
    args = parser.parse_args()

    if args.id:
        ok = process_item(args.id)
        print("answered" if ok else "skipped")
        return

    if args.once:
        n = process_all_pending()
        print(f"answered {n}")
        return

    print("agent-chat worker: polling…", flush=True)
    while True:
        try:
            n = process_all_pending()
            if n:
                print(f"answered {n}", flush=True)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr, flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

"""Poll an Evo run and keep its ResearchOS text report up to date."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from koi.adapters.paths import repo_root
from koi.evolution.importer import sync_live_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_id")
    parser.add_argument("board_id")
    parser.add_argument("card_id")
    parser.add_argument("run_path")
    parser.add_argument("--title", default="Evo live stream")
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    root = repo_root(args.project_id) / args.run_path
    while True:
        result = sync_live_report(args.project_id, args.board_id, args.card_id, args.title, args.run_path)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            return
        graph = root / "graph.json"
        payload = json.loads(graph.read_text(encoding="utf-8")) if graph.is_file() else {}
        statuses = [node.get("status") for node in (payload.get("nodes") or {}).values() if node.get("id") != "root"]
        if statuses and all(status in {"completed", "failed", "pruned", "rejected"} for status in statuses):
            return
        time.sleep(max(0.2, args.interval))


if __name__ == "__main__":
    main()

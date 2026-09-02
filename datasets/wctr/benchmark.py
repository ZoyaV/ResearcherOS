"""Dependency-free held-out wCTR benchmark for the Evo smoke run."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent


def rows(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "test"), default="test")
    args = parser.parse_args()
    train = rows("train.csv")
    evaluate = rows(f"{args.split}.csv")
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in train:
        key = (row["format"], row["device"])
        totals[key][0] += int(row["clicks"])
        totals[key][1] += int(row["impressions"])
    global_rate = sum(int(r["clicks"]) for r in train) / sum(int(r["impressions"]) for r in train)
    losses: list[float] = []
    predicted_clicks = 0.0
    actual_clicks = 0
    total_impressions = 0
    for row in evaluate:
        key = (row["format"], row["device"])
        clicks, impressions = totals.get(key, [0, 0])
        rate = (clicks + 1) / (impressions + 2) if impressions else global_rate
        rate = min(max(rate, 1e-6), 1 - 1e-6)
        actual = int(row["clicks"])
        n = int(row["impressions"])
        losses.append(-(actual * math.log(rate) + (n - actual) * math.log(1 - rate)) / n)
        predicted_clicks += rate * n
        actual_clicks += actual
        total_impressions += n
    loss = sum(losses) / len(losses)
    result = {
        "split": args.split,
        "rows": len(evaluate),
        "log_loss": loss,
        "predicted_wctr": predicted_clicks / total_impressions,
        "observed_wctr": actual_clicks / total_impressions,
        "score": -loss,
        "tasks": [{"id": f"{args.split}-wctr", "score": -loss}],
    }
    result_path = os.environ.get("EVO_RESULT_PATH")
    if result_path:
        Path(result_path).write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

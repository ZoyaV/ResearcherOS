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


def write_graph(result: dict[str, object], train: list[dict[str, str]], evaluate: list[dict[str, str]]) -> None:
    """Write a dependency-free SVG so ResearchOS can show the live metric."""
    totals = sum(int(row["impressions"]) for row in train)
    train_observed = sum(int(row["clicks"]) for row in train) / totals
    width, height = 640, 300
    bars = [("train observed", train_observed), ("test observed", float(result["observed_wctr"])), ("test predicted", float(result["predicted_wctr"]))]
    scale = 1900
    rects = []
    labels = []
    for idx, (label, value) in enumerate(bars):
        x = 70 + idx * 185
        bar_h = max(2, round(value * scale))
        y = 235 - bar_h
        rects.append(f'<rect x="{x}" y="{y}" width="110" height="{bar_h}" rx="6" fill="#4f46e5"/>')
        labels.append(f'<text x="{x + 55}" y="260" text-anchor="middle" font-size="13" fill="#334155">{label}</text>')
        labels.append(f'<text x="{x + 55}" y="{y - 8}" text-anchor="middle" font-size="14" fill="#0f172a">{value:.3f}</text>')
    svg = ''.join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="32" y="34" font-size="20" font-family="sans-serif" fill="#0f172a">wCTR held-out smoke</text>',
        '<line x1="45" y1="235" x2="600" y2="235" stroke="#94a3b8"/>',
        ''.join(rects), ''.join(labels), '</svg>'
    ])
    worktree = Path(os.environ.get("EVO_WORKTREE") or ".")
    artifact_dir = Path(os.environ.get("EVO_ARTIFACTS_DIR") or (worktree / "runs/evo-artifacts"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    exp_id = os.environ.get("EVO_EXPERIMENT_ID") or "direct"
    (artifact_dir / f"wctr-{exp_id}.svg").write_text(svg, encoding="utf-8")


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
    write_graph(result, train, evaluate)
    result_path = os.environ.get("EVO_RESULT_PATH")
    if result_path:
        Path(result_path).write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

"""Safety gate: train/test must exist and have disjoint impression ids."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).parent


def ids(name: str) -> set[str]:
    with (ROOT / name).open(newline="", encoding="utf-8") as fh:
        return {row["impression_id"] for row in csv.DictReader(fh)}


train, test = ids("train.csv"), ids("test.csv")
if not train or not test:
    raise SystemExit("train and test must both contain rows")
overlap = train & test
if overlap:
    raise SystemExit(f"train/test leakage: {sorted(overlap)}")
print(f"gate passed: train={len(train)} test={len(test)} overlap=0")

#!/usr/bin/env python3
"""Write demo template projects into the workspace if missing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from koi.adapters.repository import seed_templates  # noqa: E402


def main() -> int:
    seed_templates()
    print("Demo projects seeded (if missing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

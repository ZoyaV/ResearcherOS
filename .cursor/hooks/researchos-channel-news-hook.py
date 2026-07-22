#!/usr/bin/env python3
"""Remind agent to run researchos-channel-news after README edits."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REMINDER = (
    "## ResearchOS channel news\n"
    "Ты правил(а) `README.md`. Если это строка в § **News** (или новый product-ship), "
    "параллельно подготовь пост для Telegram `@researcher_os` по скиллу "
    "`researchos-channel-news`: README + caption + критик прозы + UI-скрин → "
    "показ пользователю → publish только после OK. "
    "Не публикуй эксперименты; не вызывай `publish.py --send` без явного ok."
)


def _paths_from_payload(payload: dict) -> list[str]:
    found: list[str] = []
    stack: list[object] = [payload]
    keys = {
        "file_path",
        "filePath",
        "path",
        "target_file",
        "targetFile",
        "uri",
        "file",
    }
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k in keys and isinstance(v, str):
                    found.append(v)
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return found


def _is_readme(path: str) -> bool:
    name = Path(path.split("?")[0]).name.lower()
    return name == "readme.md"


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print("{}")
        return

    paths = _paths_from_payload(payload)
    if not any(_is_readme(p) for p in paths):
        print("{}")
        return

    print(
        json.dumps(
            {"additional_context": REMINDER},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

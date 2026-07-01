from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_-]*", (text or "").lower())


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def _default_progress(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[review_agent {timestamp}] {message}")


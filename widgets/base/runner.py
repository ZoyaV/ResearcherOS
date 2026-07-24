"""Run a widget's optional ``backend/fetch.py`` (``fetch() -> dict``)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from widgets.base.registry import resolve_widget_dir


def run_widget_fetch(widget_key_or_id: str) -> dict[str, Any]:
    """Load ``backend/fetch.py`` from the widget package and call ``fetch()``."""
    root = resolve_widget_dir(widget_key_or_id)
    if root is None:
        raise KeyError(f"unknown widget: {widget_key_or_id}")

    fetch_path = root / "backend" / "fetch.py"
    if not fetch_path.is_file():
        raise FileNotFoundError(f"widget has no backend/fetch.py: {widget_key_or_id}")

    module_name = f"koi_widget_backend_{root.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, fetch_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {fetch_path}")

    module = importlib.util.module_from_spec(spec)
    # Ensure widget dir is importable for local helpers
    root_str = str(root)
    sys.path.insert(0, root_str)
    try:
        spec.loader.exec_module(module)
        fetch = getattr(module, "fetch", None)
        if not callable(fetch):
            raise AttributeError("backend/fetch.py must define fetch() -> dict")
        result = fetch()
    finally:
        if sys.path and sys.path[0] == root_str:
            sys.path.pop(0)

    if not isinstance(result, dict):
        raise TypeError("fetch() must return a dict")
    return result

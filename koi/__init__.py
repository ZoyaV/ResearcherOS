"""KOI package exports.

This module stays lightweight so subcommands such as ``python -m koi.review_agent``
can run without importing the full API/model stack up front.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "ExperimentCard",
    "KanbanBoard",
    "KanbanColumn",
    "Node",
    "NodeType",
    "Project",
    "Verdict",
]


def __getattr__(name: str):
    if name in __all__:
        models = import_module("koi.core.models")
        return getattr(models, name)
    raise AttributeError(f"module 'koi' has no attribute {name!r}")

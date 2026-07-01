"""Compatibility shim — use koi.adapters.done_research_queue."""
import sys

from koi.adapters import done_research_queue as _module

sys.modules[__name__] = _module

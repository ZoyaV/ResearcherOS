"""Compatibility shim — use koi.adapters.research_store."""
import sys

from koi.adapters import research_store as _module

sys.modules[__name__] = _module

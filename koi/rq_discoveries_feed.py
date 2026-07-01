"""Compatibility shim — use koi.adapters.rq_discoveries_feed."""
import sys

from koi.adapters import rq_discoveries_feed as _module

sys.modules[__name__] = _module

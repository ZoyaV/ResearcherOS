"""Compatibility shim — use koi.adapters.project_sync_queue."""
import sys

from koi.adapters import project_sync_queue as _module

sys.modules[__name__] = _module

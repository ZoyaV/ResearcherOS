"""Compatibility shim — use koi.adapters.project_sync."""
import sys

from koi.adapters import project_sync as _module

sys.modules[__name__] = _module

"""Compatibility shim — use koi.adapters.workspace."""
import sys

from koi.adapters import workspace as _module

sys.modules[__name__] = _module

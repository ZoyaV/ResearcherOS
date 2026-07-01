"""Compatibility shim — use koi.adapters.settings_store."""
import sys

from koi.adapters import settings_store as _module

sys.modules[__name__] = _module

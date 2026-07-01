"""Compatibility shim — use koi.adapters.repository."""
import sys

from koi.adapters import repository as _module

sys.modules[__name__] = _module

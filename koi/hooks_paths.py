"""Compatibility shim — use koi.adapters.hooks_paths."""
import sys

from koi.adapters import hooks_paths as _module

sys.modules[__name__] = _module

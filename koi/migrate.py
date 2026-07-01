"""Compatibility shim — use koi.core.migrate."""
import sys

from koi.core import migrate as _module

sys.modules[__name__] = _module

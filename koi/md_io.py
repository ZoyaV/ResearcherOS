"""Compatibility shim — use koi.core.md_io."""
import sys

from koi.core import md_io as _module

sys.modules[__name__] = _module

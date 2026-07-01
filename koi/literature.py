"""Compatibility shim — use koi.services.literature."""
import sys

from koi.services import literature as _module

sys.modules[__name__] = _module

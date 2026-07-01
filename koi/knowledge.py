"""Compatibility shim — use koi.services.knowledge."""
import sys

from koi.services import knowledge as _module

sys.modules[__name__] = _module

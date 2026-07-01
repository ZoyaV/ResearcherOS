"""Compatibility shim — use koi.services.programs."""
import sys

from koi.services import programs as _module

sys.modules[__name__] = _module

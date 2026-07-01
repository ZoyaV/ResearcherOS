"""Compatibility shim — use koi.services.api_helpers."""
import sys

from koi.services import api_helpers as _module

sys.modules[__name__] = _module

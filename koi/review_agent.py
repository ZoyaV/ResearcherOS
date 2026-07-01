"""Compatibility shim — use koi.services.review_agent."""
import sys

from koi.services import review_agent as _module

sys.modules[__name__] = _module

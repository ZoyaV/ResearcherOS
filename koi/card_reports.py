"""Compatibility shim — use koi.adapters.card_reports."""
import sys

from koi.adapters import card_reports as _module

sys.modules[__name__] = _module

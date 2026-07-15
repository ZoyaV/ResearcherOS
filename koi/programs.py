"""Compatibility shim — use :mod:`koi.laboratory.programs`."""
import sys

from koi.laboratory import programs as _module

sys.modules[__name__] = _module

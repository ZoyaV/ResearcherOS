"""Compatibility shim — use koi.services.rq_discoveries."""
import sys

from koi.services import rq_discoveries as _module

sys.modules[__name__] = _module

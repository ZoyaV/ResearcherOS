"""Compatibility shim — use koi.core.models."""
import sys

from koi.core import models as _module

sys.modules[__name__] = _module

"""Compatibility shim — use koi.services.paper_generator."""
import sys

from koi.services import paper_generator as _module

sys.modules[__name__] = _module

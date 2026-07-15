"""Compatibility shim — use :mod:`koi.projects.discoveries`."""
import sys

from koi.projects import discoveries as _module

sys.modules[__name__] = _module

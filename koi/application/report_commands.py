"""Compatibility shim — use :mod:`koi.projects.reports`."""

import sys

from koi.projects import reports as _module

sys.modules[__name__] = _module

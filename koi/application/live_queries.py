"""Compatibility shim — use :mod:`koi.projects.live`."""

import sys

from koi.projects import live as _module

sys.modules[__name__] = _module

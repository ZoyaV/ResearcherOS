"""Compatibility shim — use :mod:`koi.projects.views`."""

import sys

from koi.projects import views as _module

sys.modules[__name__] = _module

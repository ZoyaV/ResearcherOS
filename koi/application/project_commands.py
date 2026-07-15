"""Compatibility shim — use :mod:`koi.projects.commands`."""

import sys

from koi.projects import commands as _module

sys.modules[__name__] = _module

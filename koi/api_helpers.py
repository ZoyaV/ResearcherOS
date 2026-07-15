"""Compatibility shim — use koi.application.project_views."""
import sys

from koi.application import project_views as _module

sys.modules[__name__] = _module

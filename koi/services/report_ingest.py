"""Compatibility facade — use :mod:`koi.projects.report_ingest`."""
import sys

from koi.projects import report_ingest as _module

sys.modules[__name__] = _module

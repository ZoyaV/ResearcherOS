"""Compatibility shim — use koi.services.report_ingest."""
import sys

from koi.services import report_ingest as _module

sys.modules[__name__] = _module

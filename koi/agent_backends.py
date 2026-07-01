"""Compatibility shim — use koi.adapters.agent_backends."""
import sys

from koi.adapters import agent_backends as _module

sys.modules[__name__] = _module

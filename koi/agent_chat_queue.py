"""Compatibility shim — use koi.adapters.agent_chat_queue."""
import sys

from koi.adapters import agent_chat_queue as _module

sys.modules[__name__] = _module

"""Compatibility shim — use koi.services.agent_chat_auto."""
import sys

from koi.services import agent_chat_auto as _module

sys.modules[__name__] = _module

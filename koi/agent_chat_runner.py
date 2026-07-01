"""Compatibility shim — use koi.services.agent_chat_runner."""
import sys

from koi.services import agent_chat_runner as _module

sys.modules[__name__] = _module

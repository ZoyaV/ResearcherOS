"""Compatibility shim — use koi.services.agent_chat_inbox."""
import sys

from koi.services import agent_chat_inbox as _module

sys.modules[__name__] = _module

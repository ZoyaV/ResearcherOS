"""Compatibility shim — use koi.services.agent_chat_format."""
import sys

from koi.services import agent_chat_format as _module

sys.modules[__name__] = _module

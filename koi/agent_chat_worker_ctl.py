"""Compatibility shim — use koi.services.agent_chat_worker_ctl."""
import sys

from koi.services import agent_chat_worker_ctl as _module

sys.modules[__name__] = _module

"""Local paper collaboration: CRDT session + filesystem bridge (Spike A)."""

from koi.paper.collaboration.ids import document_id, room_id
from koi.paper.collaboration.session import (
    CollabConflict,
    CollabSession,
    get_session,
    get_or_create_session,
    live_text,
    register_agent_task,
    shutdown_all_sessions,
)

__all__ = (
    "CollabConflict",
    "CollabSession",
    "document_id",
    "get_or_create_session",
    "get_session",
    "live_text",
    "register_agent_task",
    "room_id",
    "shutdown_all_sessions",
)

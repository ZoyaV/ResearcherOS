from __future__ import annotations

from fastapi import APIRouter

from koi.services.cursor_app import cursor_is_active
from koi.services.cursor_usage import fetch_cursor_usage

router = APIRouter(tags=["cursor"])


@router.get("/cursor/usage")
def get_cursor_usage() -> dict:
    payload = fetch_cursor_usage().to_dict()
    payload["cursor_active"] = cursor_is_active()
    return payload

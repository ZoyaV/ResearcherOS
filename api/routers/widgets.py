"""HTTP API for ResearchOS widgets (discovered from koi-structure)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from widgets.base.registry import list_widgets, set_widget_enabled

router = APIRouter(tags=["widgets"])


class WidgetEnableBody(BaseModel):
    enabled: bool = Field(..., description="Whether the widget should be active")


@router.get("/widgets")
def get_widgets() -> dict:
    rows = list_widgets(ok_only=True)
    return {
        "widgets": [r.to_public_dict() for r in rows],
        "enabled": [r.key for r in rows if r.enabled],
    }


@router.get("/widgets/{project_id}/{widget_id}/data")
def get_widget_data(project_id: str, widget_id: str) -> dict:
    """Run the widget's ``backend/fetch.py`` and return its payload."""
    from widgets.base.runner import run_widget_fetch

    key = f"{project_id}/{widget_id}"
    try:
        return run_widget_fetch(key)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface fetch errors to UI
        raise HTTPException(502, f"widget fetch failed: {exc}") from exc


@router.put("/widgets/{project_id}/{widget_id}")
def put_widget(project_id: str, widget_id: str, body: WidgetEnableBody) -> dict:
    key = f"{project_id}/{widget_id}"
    try:
        rec = set_widget_enabled(key, body.enabled)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return rec.to_public_dict()

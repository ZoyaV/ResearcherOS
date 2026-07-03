from __future__ import annotations

from fastapi import APIRouter, HTTPException

from koi.services.composite import composite_to_client, list_composites_summary, load_composite

router = APIRouter(tags=["composites"])


@router.get("/composites")
def list_composites() -> list[dict]:
    return list_composites_summary()


@router.get("/composites/{composite_id}")
def get_composite(composite_id: str) -> dict:
    composite = load_composite(composite_id)
    if composite is None:
        raise HTTPException(404, "Composite not found or fewer than two members")
    return composite_to_client(composite)

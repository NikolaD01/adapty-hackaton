"""Served-flow lookup route for the demo (owner C)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.proposals import LookupIn, LookupOut

router = APIRouter(tags=["lookup (C)"])


@router.post("/apps/{app_id}/lookup", response_model=LookupOut)
async def lookup(app_id: str, body: LookupIn) -> LookupOut:
    raise not_implemented("lookup")

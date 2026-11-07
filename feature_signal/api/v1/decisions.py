"""Decision log routes (owner C)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.proposals import DecisionOut

router = APIRouter(tags=["decisions (C)"])


@router.get("/apps/{app_id}/decisions", response_model=list[DecisionOut])
async def list_decisions(app_id: str) -> list[DecisionOut]:
    raise not_implemented("list_decisions")

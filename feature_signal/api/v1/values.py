"""Value routes (owner A)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.rules import RecomputeOut, ValuesPage

router = APIRouter(tags=["values (A)"])


@router.post("/apps/{app_id}/values:recompute", response_model=RecomputeOut)
async def recompute_values(app_id: str) -> RecomputeOut:
    raise not_implemented("recompute_values")


@router.get("/apps/{app_id}/values", response_model=ValuesPage)
async def list_values(
    app_id: str, rule_key: str | None = None, limit: int = 100, cursor: str | None = None
) -> ValuesPage:
    raise not_implemented("list_values")

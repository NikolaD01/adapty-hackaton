"""Rule routes (owner A)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.rules import RuleIn, RuleOut

router = APIRouter(tags=["rules (A)"])


@router.post("/apps/{app_id}/rules", response_model=RuleOut)
async def save_rule(app_id: str, body: RuleIn) -> RuleOut:
    raise not_implemented("save_rule")


@router.get("/apps/{app_id}/rules", response_model=list[RuleOut])
async def list_rules(app_id: str) -> list[RuleOut]:
    raise not_implemented("list_rules")

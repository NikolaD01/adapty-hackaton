"""Rule suggestions and insight routes (owner B)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.insights import InsightRunIn, InsightRunOut
from feature_signal.schemas.rules import RuleSuggestionsOut

router = APIRouter(tags=["brain (B)"])


@router.post("/apps/{app_id}/rules:suggest", response_model=RuleSuggestionsOut)
async def suggest_rules(app_id: str) -> RuleSuggestionsOut:
    raise not_implemented("suggest_rules")


@router.post("/apps/{app_id}/insights:run", response_model=InsightRunOut)
async def run_insights(app_id: str, body: InsightRunIn) -> InsightRunOut:
    raise not_implemented("run_insights")


@router.get("/apps/{app_id}/insights/latest", response_model=InsightRunOut)
async def latest_insights(app_id: str) -> InsightRunOut:
    raise not_implemented("latest_insights")

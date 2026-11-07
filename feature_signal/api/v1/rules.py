"""Rule routes (owner A)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.errors import ApiError
from feature_signal.db.session import get_session
from feature_signal.repositories.event_types import EventTypeRepository
from feature_signal.repositories.features import FeatureRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.schemas.rules import RuleIn, RuleOut
from feature_signal.services.rule_service import RuleRefError, RuleService

router = APIRouter(tags=["rules (A)"])


def rule_service(session: Annotated[AsyncSession, Depends(get_session)]) -> RuleService:
    return RuleService(
        RuleRepository(session), EventTypeRepository(session), FeatureRepository(session), session.commit
    )


Rules = Annotated[RuleService, Depends(rule_service)]


@router.post("/apps/{app_id}/rules", response_model=RuleOut)
async def save_rule(app_id: str, body: RuleIn, svc: Rules) -> RuleOut:
    try:
        return await svc.save(app_id, body)
    except RuleRefError as e:
        raise ApiError(422, e.code, str(e), {"keys": e.keys}) from e


@router.get("/apps/{app_id}/rules", response_model=list[RuleOut])
async def list_rules(app_id: str, svc: Rules) -> list[RuleOut]:
    return await svc.list(app_id)

"""Value routes (owner A)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.errors import ApiError
from feature_signal.db.session import get_session
from feature_signal.repositories.events import EventRepository
from feature_signal.repositories.features import FeatureRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.repositories.tiers import TierRepository
from feature_signal.repositories.values import ValueRepository
from feature_signal.schemas.events import FeatureProfileOut
from feature_signal.schemas.rules import RecomputeOut, ValueItem, ValuesPage
from feature_signal.services.value_service import ValueService

router = APIRouter(tags=["values (A)"])


def value_service(session: AsyncSession) -> ValueService:
    return ValueService(
        EventRepository(session),
        RuleRepository(session),
        ValueRepository(session),
        FeatureRepository(session),
        TierRepository(session),
        session.commit,
    )


def value_service_dep(session: Annotated[AsyncSession, Depends(get_session)]) -> ValueService:
    return value_service(session)


Values = Annotated[ValueService, Depends(value_service_dep)]


@router.post("/apps/{app_id}/values:recompute", response_model=RecomputeOut)
async def recompute_values(app_id: str, svc: Values) -> RecomputeOut:
    users, rules = await svc.recompute_all(app_id)
    return RecomputeOut(users=users, rules=rules)


@router.get("/apps/{app_id}/values", response_model=ValuesPage)
async def list_values(
    app_id: str,
    svc: Values,
    rule_key: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    cursor: str | None = None,
) -> ValuesPage:
    if cursor is not None and not cursor.isdigit():
        raise ApiError(422, "bad_cursor", "cursor must come from next_cursor")
    offset = int(cursor or 0)
    rows, more = await svc.values.page(app_id, rule_key, limit, offset)
    return ValuesPage(
        items=[
            ValueItem(
                customer_user_id=r.customer_user_id, rule_key=r.rule_key, value=r.value, computed_at=r.computed_at
            )
            for r in rows
        ],
        next_cursor=str(offset + limit) if more else None,
    )


@router.get("/apps/{app_id}/users/{customer_user_id}/features", response_model=FeatureProfileOut)
async def user_feature_profile(app_id: str, customer_user_id: str, svc: Values) -> FeatureProfileOut:
    return await svc.profile(app_id, customer_user_id)

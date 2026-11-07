"""Features and event catalog routes (owner A)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.errors import ApiError
from feature_signal.db.session import get_session
from feature_signal.repositories.event_types import EventTypeRepository
from feature_signal.repositories.features import FeatureRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.schemas.events import EventTypeIn, EventTypeOut, FeatureIn, FeatureOut
from feature_signal.services.catalog_service import CatalogService, UnknownFeaturesError

router = APIRouter(tags=["catalog (A)"])


def catalog_service(session: Annotated[AsyncSession, Depends(get_session)]) -> CatalogService:
    return CatalogService(
        FeatureRepository(session), EventTypeRepository(session), RuleRepository(session), session.commit
    )


Svc = Annotated[CatalogService, Depends(catalog_service)]


@router.post("/apps/{app_id}/event-types", response_model=EventTypeOut)
async def register_event_type(app_id: str, body: EventTypeIn, svc: Svc) -> EventTypeOut:
    try:
        return await svc.register_event_type(app_id, body)
    except UnknownFeaturesError as e:
        raise ApiError(422, "unknown_feature", str(e), {"features": e.keys}) from e


@router.get("/apps/{app_id}/event-types", response_model=list[EventTypeOut])
async def list_event_types(app_id: str, svc: Svc) -> list[EventTypeOut]:
    return await svc.list_event_types(app_id)


@router.post("/apps/{app_id}/features", response_model=FeatureOut)
async def register_feature(app_id: str, body: FeatureIn, svc: Svc) -> FeatureOut:
    return await svc.register_feature(app_id, body)


@router.get("/apps/{app_id}/features", response_model=list[FeatureOut])
async def list_features(app_id: str, svc: Svc) -> list[FeatureOut]:
    return await svc.list_features(app_id)

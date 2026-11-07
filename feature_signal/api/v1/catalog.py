"""Event catalog routes (owner A)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.events import EventTypeIn, EventTypeOut, FeatureIn, FeatureOut

router = APIRouter(tags=["catalog (A)"])


@router.post("/apps/{app_id}/event-types", response_model=EventTypeOut)
async def register_event_type(app_id: str, body: EventTypeIn) -> EventTypeOut:
    raise not_implemented("register_event_type")


@router.get("/apps/{app_id}/event-types", response_model=list[EventTypeOut])
async def list_event_types(app_id: str) -> list[EventTypeOut]:
    raise not_implemented("list_event_types")


@router.post("/apps/{app_id}/features", response_model=FeatureOut)
async def register_feature(app_id: str, body: FeatureIn) -> FeatureOut:
    raise not_implemented("register_feature")


@router.get("/apps/{app_id}/features", response_model=list[FeatureOut])
async def list_features(app_id: str) -> list[FeatureOut]:
    raise not_implemented("list_features")

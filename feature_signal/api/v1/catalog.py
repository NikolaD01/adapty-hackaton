"""Event catalog routes (owner A)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.events import EventTypeIn, EventTypeOut

router = APIRouter(tags=["catalog (A)"])


@router.post("/apps/{app_id}/event-types", response_model=EventTypeOut)
async def register_event_type(app_id: str, body: EventTypeIn) -> EventTypeOut:
    raise not_implemented("register_event_type")


@router.get("/apps/{app_id}/event-types", response_model=list[EventTypeOut])
async def list_event_types(app_id: str) -> list[EventTypeOut]:
    raise not_implemented("list_event_types")

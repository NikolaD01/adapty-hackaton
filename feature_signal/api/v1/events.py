"""Event ingest and timeline routes (owner A)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.events import EventBatchIn, EventBatchOut, TimelineOut

router = APIRouter(tags=["events (A)"])


@router.post("/apps/{app_id}/events", response_model=EventBatchOut)
async def ingest_events(app_id: str, body: EventBatchIn) -> EventBatchOut:
    raise not_implemented("ingest_events")


@router.get("/apps/{app_id}/users/{customer_user_id}/timeline", response_model=TimelineOut)
async def user_timeline(app_id: str, customer_user_id: str, limit: int = 50) -> TimelineOut:
    raise not_implemented("user_timeline")

"""Event ingest and timeline routes (owner A)."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.api.v1.values import value_service
from feature_signal.db.session import get_session
from feature_signal.domain.models import Event
from feature_signal.repositories.events import EventRepository
from feature_signal.schemas.events import EventBatchIn, EventBatchOut, TimelineItem, TimelineOut
from feature_signal.services.ingest_service import IngestService, run_membership_sync

router = APIRouter(tags=["events (A)"])


def ingest_service(session: Annotated[AsyncSession, Depends(get_session)]) -> IngestService:
    return IngestService(EventRepository(session), session.commit, value_service(session).recompute_users)


Ingest = Annotated[IngestService, Depends(ingest_service)]


@router.post("/apps/{app_id}/events", response_model=EventBatchOut)
async def ingest_events(
    app_id: str, body: EventBatchIn, svc: Ingest, request: Request, background: BackgroundTasks
) -> EventBatchOut:
    events = [
        Event(
            event_id=str(e.event_id),
            customer_user_id=e.customer_user_id,
            key=e.key,
            occurred_at=e.occurred_at,
            props=dict(e.props),
            decision_id=e.decision_id,
        )
        for e in body.events
    ]
    result, users = await svc.ingest(app_id, events)
    # C registers its MembershipSync on app.state.membership_sync; until then this is a no-op.
    background.add_task(run_membership_sync, getattr(request.app.state, "membership_sync", None), app_id, users)
    return EventBatchOut(accepted=result.accepted, duplicates=result.duplicates, unknown_keys=result.unknown_keys)


@router.get("/apps/{app_id}/users/{customer_user_id}/timeline", response_model=TimelineOut)
async def user_timeline(
    app_id: str,
    customer_user_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> TimelineOut:
    events = await EventRepository(session).recent(app_id, customer_user_id, limit)
    return TimelineOut(
        customer_user_id=customer_user_id,
        items=[
            TimelineItem(
                event_id=e.event_id, key=e.key, occurred_at=e.occurred_at, received_at=e.received_at, props=e.props
            )
            for e in events
        ],
    )

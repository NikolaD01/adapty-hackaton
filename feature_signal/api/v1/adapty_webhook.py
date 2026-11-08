"""Adapty webhook receiver (owner A). Configure in Adapty: Integrations → Webhook →
`https://<host>/v1/apps/<app_id>/adapty-webhook`, Authorization header = ADAPTY_WEBHOOK_AUTH."""

import hmac
import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.api.v1.values import value_service
from feature_signal.core.config import get_settings
from feature_signal.core.errors import ApiError
from feature_signal.db.session import get_session
from feature_signal.repositories.event_types import EventTypeRepository
from feature_signal.repositories.events import EventRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.services import adapty_webhook_service as wh
from feature_signal.services.ingest_service import IngestService, run_membership_sync

router = APIRouter(tags=["adapty webhook (A)"])
log = logging.getLogger(__name__)


def check_auth(authorization: str | None) -> None:
    expected = get_settings().adapty_webhook_auth.get_secret_value()
    if expected and not hmac.compare_digest(authorization or "", expected):
        raise ApiError(401, "unauthorized", "wrong or missing Authorization header")


@router.post("/apps/{app_id}/adapty-webhook")
async def adapty_webhook(
    app_id: str,
    request: Request,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: Annotated[dict[str, Any], Body()] = None,  # noqa: B008 — FastAPI body
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Always 2xx for well-authenticated calls (Adapty pauses delivery after repeated failures).
    The verification request is `{}` and gets `{}` back."""
    check_auth(authorization)
    event = wh.to_event(payload or {})
    if event is None:
        return {}
    event_types = EventTypeRepository(session)
    if await event_types.get_row(app_id, event.key) is None:
        await event_types.upsert_row(
            app_id, event.key, event.key.replace("_", " "), wh.description(event.key.removeprefix(wh.PREFIX)), []
        )
    await RuleRepository(session).upsert_default(app_id, wh.net_revenue_rule())
    svc = IngestService(EventRepository(session), session.commit, value_service(session).recompute_users)
    result, users = await svc.ingest(app_id, [event])
    background.add_task(run_membership_sync, getattr(request.app.state, "membership_sync", None), app_id, users)
    return {"accepted": result.accepted, "duplicates": result.duplicates}

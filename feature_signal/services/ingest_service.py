"""Event ingest (owner A): one transaction for events + counters, then the fast loop for those users."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence

from feature_signal.domain.models import BatchResult, Event
from feature_signal.domain.ports import EventSink, MembershipSync

log = logging.getLogger(__name__)


class IngestService:
    def __init__(self, sink: EventSink, commit: Callable[[], Awaitable[None]]) -> None:
        self.sink, self.commit = sink, commit

    async def ingest(self, app_id: str, events: Sequence[Event]) -> tuple[BatchResult, list[str]]:
        """Returns the result and the users whose new events were stored (input for the fast loop)."""
        result = await self.sink.record_batch(app_id, events)
        await self.commit()
        users = sorted({e.customer_user_id for e in events}) if result.accepted else []
        return result, users


async def run_membership_sync(sync: MembershipSync | None, app_id: str, users: list[str]) -> None:
    """Background step after the ingest commit. A failure here never fails ingest."""
    if sync is None or not users:
        return
    try:
        await sync.sync_users(app_id, users)
    except Exception:  # noqa: BLE001 — logged, ingest already committed
        log.exception("membership sync failed for %d users", len(users))

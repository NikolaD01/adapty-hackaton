"""Event history repository (owner A). Implements EventSink (idempotent on event_id) and EventReader."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import case, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import EventRow, EventTypeRow, UserActionCountRow
from feature_signal.domain.models import BatchResult, Event


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _action_ids(self, app_id: str, keys: set[str]) -> dict[str, int]:
        if not keys:
            return {}
        stmt = select(EventTypeRow.key, EventTypeRow.action_id).where(
            EventTypeRow.app_id == app_id, EventTypeRow.key.in_(keys)
        )
        return {k: a for k, a in (await self.session.execute(stmt)).all()}

    async def record_batch(self, app_id: str, events: Sequence[Event]) -> BatchResult:
        """Insert new events and bump counters only for rows actually inserted. The caller commits,
        so events and counters land in one transaction."""
        ids = await self._action_ids(app_id, {e.key for e in events})
        unknown = sorted({e.key for e in events} - set(ids))
        now = datetime.now(timezone.utc)

        seen: set[str] = set()
        rows = []
        for e in events:
            if e.key not in ids or e.event_id in seen:
                continue
            seen.add(e.event_id)
            rows.append(
                {
                    "event_id": e.event_id,
                    "app_id": app_id,
                    "customer_user_id": e.customer_user_id,
                    "action_id": ids[e.key],
                    "occurred_at": e.occurred_at,
                    "received_at": now,
                    "props": dict(e.props),
                    "decision_id": e.decision_id,
                }
            )
        inserted: set[str] = set()
        if rows:
            stmt = insert(EventRow).values(rows).on_conflict_do_nothing(index_elements=["event_id"])
            inserted = set((await self.session.scalars(stmt.returning(EventRow.event_id))).all())

        counts: dict[tuple[str, int], tuple[int, datetime]] = {}
        for r in rows:
            if r["event_id"] not in inserted:
                continue
            k = (r["customer_user_id"], r["action_id"])
            n, last = counts.get(k, (0, r["occurred_at"]))
            counts[k] = (n + 1, max(last, r["occurred_at"]))
        for (user, action_id), (n, last) in counts.items():
            up = insert(UserActionCountRow).values(
                app_id=app_id, customer_user_id=user, action_id=action_id, n=n, last_ts=last
            )
            up = up.on_conflict_do_update(
                index_elements=["app_id", "customer_user_id", "action_id"],
                set_={"n": UserActionCountRow.n + n, "last_ts": _later(UserActionCountRow.last_ts, last)},
            )
            await self.session.execute(up)

        known = sum(1 for e in events if e.key in ids)
        return BatchResult(accepted=len(inserted), duplicates=known - len(inserted), unknown_keys=unknown)

    # EventReader port
    async def history(self, app_id: str, customer_user_id: str, since: datetime | None) -> list[Event]:
        stmt = (
            select(EventRow, EventTypeRow.key)
            .join(EventTypeRow, EventTypeRow.action_id == EventRow.action_id)
            .where(EventRow.app_id == app_id, EventRow.customer_user_id == customer_user_id)
            .order_by(EventRow.occurred_at)
        )
        if since is not None:
            stmt = stmt.where(EventRow.occurred_at >= since)
        return [
            Event(
                event_id=r.event_id,
                customer_user_id=r.customer_user_id,
                key=key,
                occurred_at=r.occurred_at,
                received_at=r.received_at,
                props=dict(r.props or {}),
                decision_id=r.decision_id,
            )
            for r, key in (await self.session.execute(stmt)).all()
        ]

    async def recent(self, app_id: str, customer_user_id: str, limit: int) -> list[Event]:
        """Newest first by occurred_at (phone time), for the timeline."""
        stmt = (
            select(EventRow, EventTypeRow.key)
            .join(EventTypeRow, EventTypeRow.action_id == EventRow.action_id)
            .where(EventRow.app_id == app_id, EventRow.customer_user_id == customer_user_id)
            .order_by(EventRow.occurred_at.desc(), EventRow.received_at.desc())
            .limit(limit)
        )
        return [
            Event(
                event_id=r.event_id,
                customer_user_id=r.customer_user_id,
                key=key,
                occurred_at=r.occurred_at,
                received_at=r.received_at,
                props=dict(r.props or {}),
                decision_id=r.decision_id,
            )
            for r, key in (await self.session.execute(stmt)).all()
        ]

    async def users(self, app_id: str) -> list[str]:
        stmt = select(EventRow.customer_user_id).where(EventRow.app_id == app_id).distinct()
        return sorted(await self.session.scalars(stmt))


def _later(column, value: datetime):  # noqa: ANN001, ANN202 — SQL expression
    return case((column > value, column), else_=value)

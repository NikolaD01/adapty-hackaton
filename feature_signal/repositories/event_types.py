"""Event catalog repository (owner A). Implements the EventTypeRepo port."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import EventTypeFeatureRow, EventTypeRow
from feature_signal.domain.models import EventType


class EventTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _features_of(self, action_ids: list[int]) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {a: [] for a in action_ids}
        if action_ids:
            stmt = select(EventTypeFeatureRow).where(EventTypeFeatureRow.action_id.in_(action_ids))
            for link in await self.session.scalars(stmt):
                out[link.action_id].append(link.feature_key)
        return {a: sorted(f) for a, f in out.items()}

    async def get_row(self, app_id: str, key: str) -> EventTypeRow | None:
        stmt = select(EventTypeRow).where(EventTypeRow.app_id == app_id, EventTypeRow.key == key)
        return await self.session.scalar(stmt)

    async def features_of_key(self, app_id: str, key: str) -> list[str]:
        row = await self.get_row(app_id, key)
        return (await self._features_of([row.action_id]))[row.action_id] if row else []

    async def upsert_row(
        self, app_id: str, key: str, name: str, description: str, features: list[str]
    ) -> tuple[EventTypeRow, list[str]]:
        row = await self.get_row(app_id, key)
        if row is None:
            row = EventTypeRow(app_id=app_id, key=key, created_at=datetime.now(timezone.utc))
            self.session.add(row)
        row.name, row.description = name, description
        await self.session.flush()
        await self.session.execute(delete(EventTypeFeatureRow).where(EventTypeFeatureRow.action_id == row.action_id))
        for feature in sorted(set(features)):
            self.session.add(EventTypeFeatureRow(action_id=row.action_id, feature_key=feature, app_id=app_id))
        await self.session.flush()
        return row, sorted(set(features))

    async def rows_with_features(self, app_id: str) -> list[tuple[EventTypeRow, list[str]]]:
        stmt = select(EventTypeRow).where(EventTypeRow.app_id == app_id).order_by(EventTypeRow.action_id)
        rows = list(await self.session.scalars(stmt))
        feats = await self._features_of([r.action_id for r in rows])
        return [(r, feats[r.action_id]) for r in rows]

    async def event_keys_in_feature(self, app_id: str, feature_key: str) -> list[str]:
        stmt = (
            select(EventTypeRow.key)
            .join(EventTypeFeatureRow, EventTypeFeatureRow.action_id == EventTypeRow.action_id)
            .where(EventTypeFeatureRow.app_id == app_id, EventTypeFeatureRow.feature_key == feature_key)
            .order_by(EventTypeRow.key)
        )
        return list(await self.session.scalars(stmt))

    # EventTypeRepo port
    async def upsert(self, app_id: str, key: str, name: str, description: str, features: list[str]) -> EventType:
        row, feats = await self.upsert_row(app_id, key, name, description, features)
        return EventType(
            action_id=row.action_id, key=row.key, name=row.name, description=row.description, features=feats
        )

    async def list(self, app_id: str) -> list[EventType]:
        return [
            EventType(action_id=r.action_id, key=r.key, name=r.name, description=r.description, features=f)
            for r, f in await self.rows_with_features(app_id)
        ]

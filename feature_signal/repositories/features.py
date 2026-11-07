"""Features repository (owner A). Implements the FeatureRepo port (list) plus row access for the service."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import FeatureRow
from feature_signal.domain.models import Feature


def to_domain(row: FeatureRow) -> Feature:
    return Feature(key=row.key, name=row.name, description=row.description, plans=list(row.plans or []))


class FeatureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_row(self, app_id: str, feature: Feature) -> FeatureRow:
        row = await self.session.get(FeatureRow, (app_id, feature.key))
        if row is None:
            row = FeatureRow(app_id=app_id, key=feature.key, created_at=datetime.now(timezone.utc))
            self.session.add(row)
        row.name, row.description, row.plans = feature.name, feature.description, list(feature.plans)
        await self.session.flush()
        return row

    async def rows(self, app_id: str) -> list[FeatureRow]:
        result = await self.session.scalars(
            select(FeatureRow).where(FeatureRow.app_id == app_id).order_by(FeatureRow.key)
        )
        return list(result)

    async def existing_keys(self, app_id: str, keys: list[str]) -> set[str]:
        if not keys:
            return set()
        stmt = select(FeatureRow.key).where(FeatureRow.app_id == app_id, FeatureRow.key.in_(keys))
        return set(await self.session.scalars(stmt))

    # FeatureRepo port
    async def upsert(self, app_id: str, feature: Feature) -> Feature:
        return to_domain(await self.upsert_row(app_id, feature))

    async def list(self, app_id: str) -> list[Feature]:
        return [to_domain(r) for r in await self.rows(app_id)]

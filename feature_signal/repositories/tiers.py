"""Feature tiers repository (owner A). Implements the TierStore port: B writes after a run, C reads."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import FeatureTierRow
from feature_signal.domain.models import FeatureTier


class TierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def put_many(self, app_id: str, tiers: Sequence[FeatureTier]) -> None:
        """Replace the app's tiers with the latest run (a feature that stopped passing disappears)."""
        now = datetime.now(timezone.utc)
        await self.session.execute(delete(FeatureTierRow).where(FeatureTierRow.app_id == app_id))
        for t in tiers:
            self.session.add(
                FeatureTierRow(
                    app_id=app_id,
                    feature=t.feature,
                    rule_key=t.rule_key,
                    low_max=t.low_max,
                    mid_max=t.mid_max,
                    passed=t.passed,
                    updated_at=now,
                )
            )
        await self.session.flush()

    async def list(self, app_id: str) -> list[FeatureTier]:
        rows = await self.session.scalars(
            select(FeatureTierRow).where(FeatureTierRow.app_id == app_id).order_by(FeatureTierRow.feature)
        )
        return [
            FeatureTier(feature=r.feature, rule_key=r.rule_key, low_max=r.low_max, mid_max=r.mid_max, passed=r.passed)
            for r in rows
        ]

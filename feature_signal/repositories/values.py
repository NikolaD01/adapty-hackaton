"""Values repository (owner A). Implements the ValueStore port read by B and C."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import UserValueRow
from feature_signal.domain.models import FeatureMatrix


class ValueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def put_many(self, app_id: str, rule_key: str, values: dict[str, float]) -> None:
        if not values:
            return
        now = datetime.now(timezone.utc)
        rows = [
            {"app_id": app_id, "customer_user_id": u, "rule_key": rule_key, "value": float(v), "computed_at": now}
            for u, v in values.items()
        ]
        stmt = insert(UserValueRow).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["app_id", "customer_user_id", "rule_key"],
            set_={"value": stmt.excluded.value, "computed_at": stmt.excluded.computed_at},
        )
        await self.session.execute(stmt)

    async def matrix(self, app_id: str) -> FeatureMatrix:
        rows = (
            await self.session.execute(
                select(UserValueRow.customer_user_id, UserValueRow.rule_key, UserValueRow.value).where(
                    UserValueRow.app_id == app_id
                )
            )
        ).all()
        users = sorted({u for u, _, _ in rows})
        columns = sorted({k for _, k, _ in rows})
        ui, ci = {u: i for i, u in enumerate(users)}, {c: i for i, c in enumerate(columns)}
        values = [[0.0] * len(columns) for _ in users]
        for u, k, v in rows:
            values[ui[u]][ci[k]] = v
        return FeatureMatrix(users=users, columns=columns, values=values)

    async def page(self, app_id: str, rule_key: str | None, limit: int, offset: int) -> tuple[list[UserValueRow], bool]:
        stmt = select(UserValueRow).where(UserValueRow.app_id == app_id)
        if rule_key:
            stmt = stmt.where(UserValueRow.rule_key == rule_key)
        stmt = stmt.order_by(UserValueRow.customer_user_id, UserValueRow.rule_key).offset(offset).limit(limit + 1)
        rows = list(await self.session.scalars(stmt))
        return rows[:limit], len(rows) > limit

    async def of_user(self, app_id: str, customer_user_id: str) -> dict[str, UserValueRow]:
        stmt = select(UserValueRow).where(
            UserValueRow.app_id == app_id, UserValueRow.customer_user_id == customer_user_id
        )
        return {r.rule_key: r for r in await self.session.scalars(stmt)}

    async def count(self, app_id: str) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(UserValueRow).where(UserValueRow.app_id == app_id)
        )

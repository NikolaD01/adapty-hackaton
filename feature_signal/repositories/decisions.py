"""Decision log repository (owner C). Append-only; the API on top of it is C5."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import DecisionRow


class DecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, app_id: str, proposal_id: str, decided_by: str, action: str, steps: list[dict[str, Any]]
    ) -> DecisionRow:
        row = DecisionRow(
            decision_id=f"dc_{uuid4().hex[:10]}",
            app_id=app_id,
            proposal_id=proposal_id,
            decided_by=decided_by,
            action=action,
            steps=steps,
            at=datetime.now(timezone.utc),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list(self, app_id: str, proposal_id: str | None = None) -> list[DecisionRow]:
        query = select(DecisionRow).where(DecisionRow.app_id == app_id)
        if proposal_id:
            query = query.where(DecisionRow.proposal_id == proposal_id)
        return list(await self.session.scalars(query.order_by(DecisionRow.at.desc(), DecisionRow.decision_id.desc())))

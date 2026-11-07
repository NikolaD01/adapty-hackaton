"""Proposals and per-app settings repository (owner C). Tables are defined by A in `db/tables.py`."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import AppSettingsRow, ProposalRow
from feature_signal.schemas.proposals import AppSettings


class ProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, row: ProposalRow) -> ProposalRow:
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, proposal_id: str) -> ProposalRow | None:
        return await self.session.scalar(select(ProposalRow).where(ProposalRow.proposal_id == proposal_id))

    async def list(self, app_id: str, status: str | None = None) -> list[ProposalRow]:
        query = select(ProposalRow).where(ProposalRow.app_id == app_id)
        if status:
            query = query.where(ProposalRow.status == status)
        return list(await self.session.scalars(query.order_by(ProposalRow.created_at, ProposalRow.proposal_id)))

    async def count_status(self, app_id: str, status: str) -> int:
        return len(await self.list(app_id, status))


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, app_id: str) -> AppSettings:
        row = await self.session.scalar(select(AppSettingsRow).where(AppSettingsRow.app_id == app_id))
        return AppSettings.model_validate(row.settings) if row else AppSettings()

    async def put(self, app_id: str, settings: AppSettings) -> AppSettings:
        row = await self.session.scalar(select(AppSettingsRow).where(AppSettingsRow.app_id == app_id))
        now = datetime.now(timezone.utc)
        if row is None:
            row = AppSettingsRow(app_id=app_id, settings={}, updated_at=now)
            self.session.add(row)
        row.settings = settings.model_dump(mode="json")
        row.updated_at = now
        await self.session.flush()
        return settings

"""Rules repository (owner A). Implements the RuleRepo port; definitions are stored as JSON."""

from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.tables import RuleRow
from feature_signal.domain.models import Rule, RuleDefinition, Where


def definition_to_json(d: RuleDefinition) -> dict:
    return {k: v for k, v in asdict(d).items() if v is not None}


def definition_from_json(data: dict) -> RuleDefinition:
    data = dict(data)
    if data.get("where"):
        data["where"] = Where(**data["where"])
    return RuleDefinition(**data)


def to_domain(row: RuleRow) -> Rule:
    return Rule(
        key=row.key,
        name=row.name,
        description=row.description,
        definition=definition_from_json(row.definition),
        source=row.source,
        feature=row.feature,
        rule_id=row.rule_id,
    )


class RuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_row(self, app_id: str, key: str) -> RuleRow | None:
        return await self.session.scalar(select(RuleRow).where(RuleRow.app_id == app_id, RuleRow.key == key))

    async def save_row(self, app_id: str, rule: Rule) -> RuleRow:
        row = await self.get_row(app_id, rule.key)
        if row is None:
            row = RuleRow(app_id=app_id, key=rule.key, created_at=datetime.now(timezone.utc))
            self.session.add(row)
        row.name, row.description, row.source, row.feature = rule.name, rule.description, rule.source, rule.feature
        row.definition = definition_to_json(rule.definition)
        await self.session.flush()
        return row

    async def upsert_default(self, app_id: str, rule: Rule) -> RuleRow | None:
        """Create or refresh a default rule; never overwrite a rule a human or the AI saved under that key."""
        row = await self.get_row(app_id, rule.key)
        if row is not None and row.source != "default":
            return None
        return await self.save_row(app_id, rule)

    async def rows(self, app_id: str) -> list[RuleRow]:
        return list(
            await self.session.scalars(select(RuleRow).where(RuleRow.app_id == app_id).order_by(RuleRow.rule_id))
        )

    # RuleRepo port
    async def save(self, app_id: str, rule: Rule) -> Rule:
        return to_domain(await self.save_row(app_id, rule))

    async def list(self, app_id: str) -> list[Rule]:
        return [to_domain(r) for r in await self.rows(app_id)]

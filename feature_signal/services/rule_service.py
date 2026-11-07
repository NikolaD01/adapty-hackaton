"""Rules API service (owner A): validates a rule against the catalog and saves it."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from feature_signal.domain.models import Rule, RuleDefinition, Where
from feature_signal.repositories.event_types import EventTypeRepository
from feature_signal.repositories.features import FeatureRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.schemas.rules import RuleIn, RuleOut


class RuleRefError(ValueError):
    def __init__(self, code: str, keys: list[str]) -> None:
        super().__init__(f"{code}: {', '.join(keys)}")
        self.code, self.keys = code, keys


def to_domain(body: RuleIn) -> Rule:
    d = body.definition
    where = Where(prop=d.where.prop, op=d.where.op, value=d.where.value) if d.where else None
    return Rule(
        key=body.key,
        name=body.name,
        description=body.description,
        source=body.source,
        feature=body.feature,
        definition=RuleDefinition(
            event_keys=list(d.event_keys),
            measure=d.measure,
            window_days=d.window_days,
            distinct_prop=d.distinct_prop,
            value_prop=d.value_prop,
            denominator_event_keys=d.denominator_event_keys,
            where=where,
        ),
    )


class RuleService:
    def __init__(
        self,
        rules: RuleRepository,
        event_types: EventTypeRepository,
        features: FeatureRepository,
        commit: Callable[[], Awaitable[None]],
    ) -> None:
        self.rules, self.event_types, self.features, self.commit = rules, event_types, features, commit

    async def save(self, app_id: str, body: RuleIn) -> RuleOut:
        known = {r.key for r, _ in await self.event_types.rows_with_features(app_id)}
        used = set(body.definition.event_keys) | set(body.definition.denominator_event_keys or [])
        if missing := sorted(used - known):
            raise RuleRefError("unknown_event_key", missing)
        if body.feature and not await self.features.existing_keys(app_id, [body.feature]):
            raise RuleRefError("unknown_feature", [body.feature])
        row = await self.rules.save_row(app_id, to_domain(body))
        await self.commit()
        return self._out(row)

    async def list(self, app_id: str) -> list[RuleOut]:
        return [self._out(r) for r in await self.rules.rows(app_id)]

    @staticmethod
    def _out(row) -> RuleOut:  # noqa: ANN001 — RuleRow
        return RuleOut(
            rule_id=row.rule_id,
            key=row.key,
            name=row.name,
            description=row.description,
            source=row.source,
            feature=row.feature,
            definition=row.definition,
            value_type=row.value_type or "float",
            created_at=row.created_at,
        )

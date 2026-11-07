"""Features and event catalog (owner A). Keeps each feature's default rules in step with its events."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from feature_signal.domain.models import Feature
from feature_signal.domain.rules import default_rules
from feature_signal.repositories.event_types import EventTypeRepository
from feature_signal.repositories.features import FeatureRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.schemas.events import EventTypeIn, EventTypeOut, FeatureIn, FeatureOut


class UnknownFeaturesError(ValueError):
    def __init__(self, keys: list[str]) -> None:
        super().__init__(f"unknown feature keys: {', '.join(keys)}")
        self.keys = keys


class CatalogService:
    def __init__(
        self,
        features: FeatureRepository,
        event_types: EventTypeRepository,
        rules: RuleRepository,
        commit: Callable[[], Awaitable[None]],
    ) -> None:
        self.features, self.event_types, self.rules, self.commit = features, event_types, rules, commit

    async def _sync_defaults(self, app_id: str, feature_key: str, feature_name: str) -> None:
        events = await self.event_types.event_keys_in_feature(app_id, feature_key)
        for rule in default_rules(feature_key, feature_name, events):
            await self.rules.upsert_default(app_id, rule)

    async def register_feature(self, app_id: str, body: FeatureIn) -> FeatureOut:
        row = await self.features.upsert_row(
            app_id, Feature(key=body.key, name=body.name, description=body.description, plans=body.plans)
        )
        await self._sync_defaults(app_id, row.key, row.name)
        await self.commit()
        return FeatureOut(
            key=row.key, name=row.name, description=row.description, plans=list(row.plans), created_at=row.created_at
        )

    async def list_features(self, app_id: str) -> list[FeatureOut]:
        return [
            FeatureOut(key=r.key, name=r.name, description=r.description, plans=list(r.plans), created_at=r.created_at)
            for r in await self.features.rows(app_id)
        ]

    async def register_event_type(self, app_id: str, body: EventTypeIn) -> EventTypeOut:
        wanted = sorted(set(body.features))
        missing = sorted(set(wanted) - await self.features.existing_keys(app_id, wanted))
        if missing:
            raise UnknownFeaturesError(missing)
        before = await self.event_types.features_of_key(app_id, body.key)
        row, feats = await self.event_types.upsert_row(app_id, body.key, body.name, body.description, wanted)
        names = {r.key: r.name for r in await self.features.rows(app_id)}
        for feature_key in sorted(set(before) | set(feats)):
            await self._sync_defaults(app_id, feature_key, names.get(feature_key, feature_key))
        await self.commit()
        return EventTypeOut(
            action_id=row.action_id,
            key=row.key,
            name=row.name,
            description=row.description,
            features=feats,
            created_at=row.created_at,
        )

    async def list_event_types(self, app_id: str) -> list[EventTypeOut]:
        return [
            EventTypeOut(
                action_id=r.action_id,
                key=r.key,
                name=r.name,
                description=r.description,
                features=f,
                created_at=r.created_at,
            )
            for r, f in await self.event_types.rows_with_features(app_id)
        ]

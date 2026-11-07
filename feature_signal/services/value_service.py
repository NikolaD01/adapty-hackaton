"""Values and feature profiles (owner A): rules applied to each user's history."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone

from feature_signal.domain.rules import apply
from feature_signal.repositories.events import EventRepository
from feature_signal.repositories.features import FeatureRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.repositories.tiers import TierRepository
from feature_signal.repositories.values import ValueRepository
from feature_signal.schemas.events import FeatureProfileItem, FeatureProfileOut


class ValueService:
    def __init__(
        self,
        events: EventRepository,
        rules: RuleRepository,
        values: ValueRepository,
        features: FeatureRepository,
        tiers: TierRepository,
        commit: Callable[[], Awaitable[None]],
    ) -> None:
        self.events, self.rules, self.values = events, rules, values
        self.features, self.tiers, self.commit = features, tiers, commit

    async def recompute_users(self, app_id: str, users: Sequence[str], now: datetime | None = None) -> int:
        """Apply every rule to each user's whole history and store the values. Returns the rule count."""
        now = now or datetime.now(timezone.utc)
        rules = await self.rules.list(app_id)
        by_rule: dict[str, dict[str, float]] = {r.key: {} for r in rules}
        for user in users:
            history = await self.events.history(app_id, user, since=None)
            for r in rules:
                by_rule[r.key][user] = apply(r.definition, history, now)
        for key, vals in by_rule.items():
            await self.values.put_many(app_id, key, vals)
        await self.commit()
        return len(rules)

    async def recompute_all(self, app_id: str) -> tuple[int, int]:
        users = await self.events.users(app_id)
        n_rules = await self.recompute_users(app_id, users)
        return len(users), n_rules

    async def profile(self, app_id: str, customer_user_id: str) -> FeatureProfileOut:
        names = {f.key: f.name for f in await self.features.list(app_id)}
        rules = [r for r in await self.rules.list(app_id) if r.feature]
        stored = await self.values.of_user(app_id, customer_user_id)
        tiers = {t.feature: t for t in await self.tiers.list(app_id) if t.passed}
        items = []
        for feature in sorted({r.feature for r in rules}):
            keys = [r.key for r in rules if r.feature == feature and r.key in stored]
            values = {k: stored[k].value for k in keys}
            tier = tiers.get(feature)
            tier_value = stored[tier.rule_key].value if tier and tier.rule_key in stored else 0.0
            items.append(
                FeatureProfileItem(
                    feature=feature,
                    name=names.get(feature, feature),
                    values=values,
                    tier=tier.tier(tier_value) if tier else None,
                    computed_at=max((stored[k].computed_at for k in keys), default=None),
                )
            )
        return FeatureProfileOut(customer_user_id=customer_user_id, features=items)

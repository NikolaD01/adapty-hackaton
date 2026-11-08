"""Read app-scoped context, propose measurements, validate, and return without saving."""

from __future__ import annotations

from collections.abc import Callable

from feature_signal.domain.models import Explanation, Ranking, Rule
from feature_signal.domain.ports import EventTypeRepo, FeatureRepo, LLMProvider, RuleRepo
from feature_signal.integrations.llm.schemas import (
    PropertyAllowlist,
    SuggestionContext,
    fallback_explanation,
    safe_explanation,
    validate_suggestions,
)


class RuleSuggestService:
    def __init__(
        self,
        *,
        feature_repo: FeatureRepo,
        event_repo: EventTypeRepo,
        rule_repo: RuleRepo,
        provider: LLMProvider | None = None,
        provider_factory: Callable[[SuggestionContext], LLMProvider] | None = None,
        property_allowlist: PropertyAllowlist | None = None,
    ):
        if (provider is None) == (provider_factory is None):
            raise ValueError("Inject exactly one provider or provider_factory")
        self.feature_repo = feature_repo
        self.event_repo = event_repo
        self.rule_repo = rule_repo
        self._provider = provider
        self._provider_factory = provider_factory
        self._properties = SuggestionContext(property_allowlist=property_allowlist).property_allowlist
        self._model_name = getattr(provider, "model_name", "")

    @property
    def model_name(self) -> str:
        return self._model_name

    async def _load(self, app_id):
        features = await self.feature_repo.list(app_id)
        catalog = await self.event_repo.list(app_id)
        rules = await self.rule_repo.list(app_id)
        context = SuggestionContext(features=features, existing_rules=rules, property_allowlist=self._properties)
        provider = self._provider_factory(context) if self._provider_factory else self._provider
        self._model_name = getattr(provider, "model_name", "")
        return catalog, context, provider

    async def suggest(self, app_id: str) -> list[tuple[Rule, str]]:
        try:
            catalog, context, provider = await self._load(app_id)
            suggestions = await provider.suggest_rules(catalog)
            return validate_suggestions(suggestions, catalog, context)
        except Exception:
            return []

    async def explain(self, app_id: str, ranking: Ranking) -> Explanation:
        try:
            catalog, _, provider = await self._load(app_id)
            return safe_explanation(ranking, await provider.explain(ranking, catalog))
        except Exception:
            return fallback_explanation(ranking)

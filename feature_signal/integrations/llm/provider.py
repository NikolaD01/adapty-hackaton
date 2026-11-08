"""OpenAI adapter. The caller owns client creation, Settings and credential handling."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from pydantic import BaseModel

from feature_signal.core.config import Settings
from feature_signal.domain.models import EventType, Explanation, Ranking, Rule
from feature_signal.integrations.llm.prompts import explanation_prompt, paywall_prompt, suggestion_prompt
from feature_signal.integrations.llm.schemas import (
    ExplanationOutput,
    PaywallCopyOutput,
    SuggestionContext,
    SuggestionsOutput,
    fallback_explanation,
    safe_explanation,
    to_domain,
    validate_suggestions,
)


class OpenAILLMProvider:
    """Implements the shared port without adding feature/property arguments to methods."""

    def __init__(self, *, settings: Settings, client: Any, context: SuggestionContext | None = None):
        self._model_name = settings.llm_model
        self._client = client
        self._context = context or SuggestionContext()

    @property
    def model_name(self) -> str:
        return self._model_name

    async def _parse(self, schema: type[BaseModel], messages: list[dict[str, str]]) -> BaseModel | None:
        response = await self._client.responses.parse(
            model=self.model_name,
            input=messages,
            text_format=schema,
            max_output_tokens=4000,
            store=False,
            timeout=30.0,
        )
        if response.status != "completed" or response.output_parsed is None:
            return None
        return schema.model_validate(response.output_parsed)

    async def suggest_rules(self, catalog: list[EventType]) -> list[tuple[Rule, str]]:
        try:
            output = await self._parse(SuggestionsOutput, suggestion_prompt(catalog, self._context))
            if output is None:
                return []
            candidates = [(to_domain(item.rule), item.rationale) for item in output.suggestions]
            return validate_suggestions(candidates, catalog, self._context)
        except Exception:
            # Timeouts, refusals, unsupported models and invalid output all mean no proposal.
            return []

    async def explain(self, ranking: Ranking, catalog: list[EventType]) -> Explanation:
        try:
            output = await self._parse(ExplanationOutput, explanation_prompt(ranking, catalog))
            return safe_explanation(ranking, output) if output else fallback_explanation(ranking)
        except Exception:
            return fallback_explanation(ranking)

    async def paywall_copy(self, segment_label: str, base_config: dict[str, Any]) -> dict[str, Any]:
        original = deepcopy(base_config)
        fields = {key: original[key] for key in ("title", "subtitle") if isinstance(original.get(key), str)}
        if not fields:
            return original
        try:
            output = await self._parse(PaywallCopyOutput, paywall_prompt(segment_label, fields))
            if output is None:
                return original
            updates = output.model_dump(exclude_none=True)
            if not updates.keys() <= fields.keys():
                return original
            for key, value in updates.items():
                # Preserve existing factual copy and reject new pricing/entitlement claims.
                if not value.strip() or re.search(r"[\d$€£%]", fields[key] + value):
                    return original
                if re.search(
                    r"\b(free|unlimited|trial|forever|lifetime|discount|price|billing|subscription|"
                    r"weekly|monthly|yearly|annual|save|off|guarantee|guaranteed)\b",
                    value,
                    re.I,
                ):
                    return original
            original.update(updates)
            return original
        except Exception:
            return original

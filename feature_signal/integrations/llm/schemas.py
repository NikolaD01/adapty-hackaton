"""Private structured-output schemas and immutable, request-scoped catalog context."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from feature_signal.domain.models import EventType, Explanation, Feature, Ranking, Rule, RuleDefinition, Where
from feature_signal.schemas.rules import RuleDefinitionIn, RuleIn, WhereIn

PropertyKind = Literal["number", "label", "boolean"]
PropertyAllowlist = Mapping[str, Mapping[str, PropertyKind]]
QualitativeHypothesis = Literal[
    "Feature usage may reflect different levels of engagement.",
    "Feature usage may reflect different user needs.",
    "Observed differences may reflect selection or other unmeasured factors.",
]


@dataclass(frozen=True)
class FeatureContext:
    key: str
    name: str
    description: str
    plans: tuple[str, ...]


@dataclass(frozen=True, init=False)
class SuggestionContext:
    """No mutable domain collections escape into a provider shared across requests.

    Property metadata is supplied by the caller, never inferred from examples or names.
    Existing definitions are immutable JSON snapshots because the shared frozen Rule
    still contains mutable event-key lists.
    """

    features: tuple[FeatureContext, ...]
    existing_rules: tuple[str, ...]
    property_allowlist: PropertyAllowlist

    def __init__(
        self,
        features: Sequence[Feature | FeatureContext] = (),
        existing_rules: Sequence[Rule] = (),
        property_allowlist: PropertyAllowlist | None = None,
    ):
        object.__setattr__(
            self, "features", tuple(FeatureContext(f.key, f.name, f.description, tuple(f.plans)) for f in features)
        )
        object.__setattr__(self, "existing_rules", tuple(json.dumps(asdict(r), sort_keys=True) for r in existing_rules))
        properties = {}
        for event, props in (property_allowlist or {}).items():
            if any(kind not in {"number", "label", "boolean"} for kind in props.values()):
                raise ValueError("Property kinds must be number, label, or boolean; free text is forbidden")
            properties[event] = MappingProxyType(dict(props))
        object.__setattr__(self, "property_allowlist", MappingProxyType(properties))


class StructuredWhere(WhereIn):
    model_config = ConfigDict(extra="forbid", strict=True)


class StructuredDefinition(RuleDefinitionIn):
    model_config = ConfigDict(extra="forbid", strict=True)
    where: StructuredWhere | None = None


class StructuredRule(RuleIn):
    model_config = ConfigDict(extra="forbid", strict=True)
    definition: StructuredDefinition


class StructuredSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    rule: StructuredRule
    rationale: str = Field(min_length=1, max_length=1000)


class SuggestionsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    suggestions: list[StructuredSuggestion] = Field(max_length=20)


class ExplanationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(min_length=1, max_length=2000)
    hypothesis: QualitativeHypothesis
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class PaywallCopyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str | None = Field(default=None, max_length=120)
    subtitle: str | None = Field(default=None, max_length=300)


def to_domain(value: RuleIn) -> Rule:
    definition = value.definition.model_dump()
    condition = definition.pop("where")
    return Rule(
        key=value.key,
        name=value.name,
        description=value.description,
        definition=RuleDefinition(**definition, where=Where(**condition) if condition else None),
        source="ai",
        feature=value.feature,
    )


def _signature(value: dict) -> str:
    definition = dict(value["definition"])
    definition["event_keys"] = sorted(set(definition["event_keys"]))
    if definition.get("denominator_event_keys"):
        definition["denominator_event_keys"] = sorted(set(definition["denominator_event_keys"]))
    return json.dumps({"feature": value.get("feature"), "definition": definition}, sort_keys=True)


def _declared(prop: str, events: Sequence[str], context: SuggestionContext, numeric: bool = False) -> bool:
    return all(
        context.property_allowlist.get(event, {}).get(prop)
        in ({"number"} if numeric else {"number", "label", "boolean"})
        for event in events
    )


def _semantic_rule(rule: Rule, catalog: Sequence[EventType], context: SuggestionContext) -> bool:
    definition = rule.definition
    events = {event.key: event for event in catalog}
    references = [*definition.event_keys, *(definition.denominator_event_keys or [])]
    if any(key not in events for key in references):
        return False
    if rule.feature is not None:
        if rule.feature not in {feature.key for feature in context.features}:
            return False
        if any(rule.feature not in events[key].features for key in references):
            return False
    if definition.measure != "ratio" and definition.denominator_event_keys is not None:
        return False
    if definition.measure != "distinct" and definition.distinct_prop is not None:
        return False
    if definition.measure not in {"sum", "last", "max", "min"} and definition.value_prop is not None:
        return False
    if definition.value_prop and not _declared(definition.value_prop, definition.event_keys, context, numeric=True):
        return False
    if definition.distinct_prop and not _declared(definition.distinct_prop, definition.event_keys, context):
        return False
    condition = definition.where
    if condition:
        if not _declared(condition.prop, references, context):
            return False
        for key in references:
            kind = context.property_allowlist[key][condition.prop]
            value = condition.value
            if kind == "number":
                if type(value) not in (int, float) or not math.isfinite(value):
                    return False
            elif kind == "label":
                if condition.op != "eq" or not isinstance(value, str) or not 0 < len(value) <= 100:
                    return False
            elif condition.op != "eq" or type(value) is not bool:
                return False
    return True


def validate_suggestions(
    candidates: object,
    catalog: Sequence[EventType],
    context: SuggestionContext,
) -> list[tuple[Rule, str]]:
    """Treat every provider as untrusted; reject bad entries without persisting anything."""
    if not isinstance(candidates, (list, tuple)) or len(candidates) > 20:
        return []
    existing = [json.loads(item) for item in context.existing_rules]
    keys = {item["key"] for item in existing}
    signatures = {_signature(item) for item in existing}
    accepted = []
    for item in candidates:
        try:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                continue
            raw, rationale = item
            if not isinstance(raw, Rule) or not isinstance(rationale, str) or not 0 < len(rationale.strip()) <= 1000:
                continue
            payload = asdict(raw)
            payload.pop("rule_id")  # Persistence identity is not part of RuleIn.
            parsed = StructuredRule.model_validate(payload)
            rule = to_domain(parsed)
            if not _semantic_rule(rule, catalog, context):
                continue
            signature = _signature(asdict(rule))
            if rule.key in keys or signature in signatures:
                continue
            keys.add(rule.key)
            signatures.add(signature)
            window = f"within {rule.definition.window_days} days" if rule.definition.window_days else "over all history"
            local_rationale = (
                f"Hypothesis: the '{rule.definition.measure}' measure over declared events {window} "
                "may describe behavioral differences. Randomized arms must establish any offer effect."
            )
            accepted.append((rule, local_rationale))
        except (ValidationError, TypeError, ValueError):
            continue
    return accepted


def fallback_explanation(ranking: Ranking) -> Explanation:
    """Render measured facts locally; generated text can never replace these numbers."""
    summary = (
        f"{ranking.feature}: net revenue in 90 days; threshold {ranking.threshold}; direction {ranking.direction}; "
        f"lift {ranking.lift}; 90% interval [{ranking.ci_low}, {ranking.ci_high}]; "
        f"holdout lift {ranking.holdout_lift}; groups {ranking.n_above} and {ranking.n_below}; "
        f"passed={ranking.passed}. Association does not establish a causal offer effect."
    )
    return Explanation(summary, "A behavioral hypothesis requires a randomized offer test.", 0.0)


def safe_explanation(ranking: Ranking, output: ExplanationOutput | Explanation) -> Explanation:
    fallback = fallback_explanation(ranking)
    try:
        value = ExplanationOutput.model_validate(
            asdict(output) if isinstance(output, Explanation) else output.model_dump()
        )
    except (ValidationError, TypeError, ValueError):
        return fallback
    # Only complete, vetted tentative statements can pass. Arbitrary natural language
    # cannot be fact-validated by keyword checks. The model's summary and confidence
    # are discarded; no calibrated hypothesis confidence exists in this contract.
    return Explanation(fallback.summary, value.hypothesis, 0.0)

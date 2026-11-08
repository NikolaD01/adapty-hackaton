"""LLM boundary tests: fakes stop at the remote structured-output call."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from feature_signal.core.config import Settings
from feature_signal.domain.models import EventType, Feature, Ranking, Rule, RuleDefinition
from feature_signal.integrations.llm.provider import OpenAILLMProvider
from feature_signal.integrations.llm.schemas import SuggestionContext
from feature_signal.schemas.rules import RuleIn


def demo_rule(**updates):
    value = {
        "key": "hd_blocked_7d",
        "name": "HD export blocked",
        "description": "HD export was blocked in the last seven days",
        "source": "ai",
        "feature": "hd_export",
        "definition": {"event_keys": ["pt_track_hd_export_blocked"], "measure": "exists", "window_days": 7},
    }
    value.update(updates)
    return value


def context():
    return SuggestionContext(
        features=[Feature("hd_export", "HD export", "Export in HD", ["pro"])],
        existing_rules=[],
        property_allowlist={"pt_track_hd_export_blocked": {"tokens_left": "number", "photo_id": "label"}},
    )


def catalog():
    return [EventType(1, "pt_track_hd_export_blocked", "Blocked export", "An export was blocked", ["hd_export"])]


class Client:
    def __init__(self, output=None, error=None, status="completed"):
        self.output = output
        self.error = error
        self.status = status
        self.calls = []
        self.responses = self

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(status=self.status, output_parsed=self.output)


def provider(client, ctx=None):
    return OpenAILLMProvider(settings=Settings(_env_file=None), client=client, context=ctx or context())


def test_blocked_hd_rule_matches_the_agreed_demo():
    assert RuleIn.model_validate(demo_rule()).definition.measure == "exists"


async def test_adapter_returns_domain_rule_and_uses_configured_structured_output():
    settings = Settings(_env_file=None)
    client = Client({"suggestions": [{"rule": demo_rule(), "rationale": "Measure blocked demand"}]})
    adapter = OpenAILLMProvider(settings=settings, client=client, context=context())
    result = await adapter.suggest_rules(catalog())
    assert result[0][0].key == "hd_blocked_7d"
    assert result[0][0].source == "ai"
    assert result[0][1] == (
        "Hypothesis: the 'exists' measure over declared events within 7 days may describe behavioral differences. "
        "Randomized arms must establish any offer effect."
    )
    call = client.calls[0]
    assert call["model"] == settings.llm_model
    assert call["text_format"].model_json_schema()["additionalProperties"] is False
    assert call["max_output_tokens"] <= 6000
    assert call["store"] is False
    prompt = str(call["input"])
    assert all(term in prompt for term in ("HD export", "Export in HD", "tokens_left", "ratio", "days_active"))


@pytest.mark.parametrize(
    "output,status,error",
    [
        (None, "completed", None),
        ({"suggestions": "bad"}, "completed", None),
        ({"suggestions": []}, "incomplete", None),
        (None, "completed", TimeoutError("offline")),
    ],
)
async def test_adapter_falls_back_on_refusal_malformed_incomplete_or_error(output, status, error):
    assert await provider(Client(output, error, status)).suggest_rules(catalog()) == []


@pytest.mark.parametrize(
    "definition",
    [
        {"event_keys": ["invented"], "measure": "count"},
        {"event_keys": ["pt_track_hd_export_blocked"], "measure": "ratio"},
        {"event_keys": ["pt_track_hd_export_blocked"], "measure": "sum"},
        {"event_keys": ["pt_track_hd_export_blocked"], "measure": "ratio", "denominator_event_keys": ["invented"]},
        {"event_keys": ["pt_track_hd_export_blocked"], "measure": "sum", "value_prop": "photo_id"},
        {"event_keys": ["pt_track_hd_export_blocked"], "measure": "distinct", "distinct_prop": "prompt"},
        {
            "event_keys": ["pt_track_hd_export_blocked"],
            "measure": "exists",
            "where": {"prop": "tokens_left", "op": "lte", "value": "zero"},
        },
        {"event_keys": ["pt_track_hd_export_blocked"], "measure": "count", "window_days": 0},
        {"event_keys": ["pt_track_hd_export_blocked"], "measure": "count", "value_prop": "tokens_left"},
    ],
)
async def test_adapter_rejects_invalid_measure_and_catalog_references(definition):
    client = Client({"suggestions": [{"rule": demo_rule(definition=definition), "rationale": "test"}]})
    assert await provider(client).suggest_rules(catalog()) == []


@pytest.mark.parametrize(
    "measure,extras",
    [
        ("ratio", {"denominator_event_keys": ["pt_track_hd_export_blocked"]}),
        ("sum", {"value_prop": "tokens_left"}),
        ("last", {"value_prop": "tokens_left"}),
        ("distinct", {"distinct_prop": "photo_id"}),
        ("exists", {"where": {"prop": "tokens_left", "op": "lte", "value": 0}}),
    ],
)
async def test_adapter_accepts_declared_composed_measures(measure, extras):
    definition = {"event_keys": ["pt_track_hd_export_blocked"], "measure": measure, **extras}
    client = Client({"suggestions": [{"rule": demo_rule(definition=definition), "rationale": "Measure usage"}]})
    assert len(await provider(client).suggest_rules(catalog())) == 1


async def test_unknown_feature_and_event_feature_mismatch_are_rejected():
    client = Client({"suggestions": [{"rule": demo_rule(feature="invented"), "rationale": "test"}]})
    assert await provider(client).suggest_rules(catalog()) == []
    client.output["suggestions"][0]["rule"]["feature"] = "hd_export"
    assert await provider(client).suggest_rules([EventType(1, catalog()[0].key, "Event", "", [])]) == []


async def test_context_snapshots_mutable_feature_rule_and_property_inputs():
    features = [Feature("hd_export", "HD export", "Known feature", ["pro"])]
    rules = [Rule("old_rule", "Old", "Old rule", RuleDefinition(["event"], "count"))]
    props = {catalog()[0].key: {"tokens_left": "number"}}
    ctx = SuggestionContext(features=features, existing_rules=rules, property_allowlist=props)
    features[0].plans.append("mutated")
    rules[0].definition.event_keys.append("mutated")
    props[catalog()[0].key]["prompt"] = "label"
    client = Client({"suggestions": []})
    await provider(client, ctx).suggest_rules(catalog())
    prompt = str(client.calls[0]["input"])
    assert "mutated" not in prompt
    assert '"prompt"' not in prompt


async def test_adapter_deduplicates_keys_and_definitions_against_existing_rules():
    existing = Rule(
        "existing", "Existing", "Same measure", RuleDefinition([catalog()[0].key], "exists", 7), feature="hd_export"
    )
    ctx = SuggestionContext(features=context().features, existing_rules=[existing])
    duplicate_key = demo_rule(key="existing", definition={"event_keys": [catalog()[0].key], "measure": "count"})
    client = Client({"suggestions": [{"rule": item, "rationale": "test"} for item in [demo_rule(), duplicate_key]]})
    assert await provider(client, ctx).suggest_rules(catalog()) == []
    client.output = {
        "suggestions": [{"rule": item, "rationale": "test"} for item in [demo_rule(), demo_rule(key="another")]]
    }
    assert len(await provider(client).suggest_rules(catalog())) == 1


def ranking():
    return Ranking("hd_export", 2.5, "up", 1.7, 1.2, 2.1, 1.4, 200, 300, True)


async def test_explanation_keeps_numeric_facts_and_rejects_invented_numbers():
    client = Client(
        {
            "summary": "Revenue is 999",
            "hypothesis": "Feature usage may reflect different user needs.",
            "confidence": 0.8,
        }
    )
    result = await provider(client).explain(ranking(), catalog())
    assert "999" not in result.summary
    assert "1.7" in result.summary
    assert "1.2" in result.summary
    assert "2.1" in result.summary
    assert result.hypothesis == "Feature usage may reflect different user needs."
    client.output["hypothesis"] = "Revenue grows by 999 percent"
    fallback = await provider(client).explain(ranking(), catalog())
    assert "999" not in fallback.hypothesis
    assert fallback.confidence == 0


async def test_explanation_failure_is_safe_and_does_not_modify_ranking():
    value = ranking()
    before = deepcopy(value)
    result = await provider(Client(error=RuntimeError("offline"))).explain(value, catalog())
    assert result.confidence == 0
    assert "net revenue" in result.summary
    assert value == before


async def test_paywall_copy_changes_only_existing_copy_and_preserves_numeric_and_billing_facts():
    base = {
        "title": "Export in HD",
        "subtitle": "For creators",
        "price": 9.99,
        "product_id": "pro_1",
        "nested": {"price": 12},
    }
    original = deepcopy(base)
    client = Client({"title": "Make every detail shine", "subtitle": "Create with confidence"})
    result = await provider(client).paywall_copy("Creators", base)
    assert result["title"] == "Make every detail shine"
    assert result["price"] == 9.99
    assert result["product_id"] == "pro_1"
    result["nested"]["price"] = 999
    assert base == original
    client.output = {"title": "Only $1 forever", "subtitle": "Unlimited free exports"}
    assert await provider(client).paywall_copy("Creators", base) == base
    assert await provider(Client(error=TimeoutError())).paywall_copy("Creators", base) == base


@pytest.mark.parametrize("measure", ["max", "min"])
async def test_numeric_extrema_use_declared_number_property(measure):
    client = Client(
        {
            "suggestions": [
                {
                    "rule": demo_rule(
                        definition={
                            "event_keys": [catalog()[0].key],
                            "measure": measure,
                            "value_prop": "tokens_left",
                        }
                    ),
                    "rationale": "Measure quota",
                }
            ]
        }
    )
    assert len(await provider(client).suggest_rules(catalog())) == 1


async def test_cross_event_property_must_be_declared_on_every_referenced_event():
    events = [*catalog(), EventType(2, "second_event", "Second", "", ["hd_export"])]
    value = demo_rule(
        definition={
            "event_keys": [catalog()[0].key, "second_event"],
            "measure": "last",
            "value_prop": "tokens_left",
        }
    )
    client = Client({"suggestions": [{"rule": value, "rationale": "test"}]})
    assert await provider(client).suggest_rules(events) == []


@pytest.mark.parametrize(
    "kind,value,op,accepted",
    [
        ("number", True, "eq", False),
        ("number", float("inf"), "eq", False),
        ("label", "short", "lte", False),
        ("label", "a" * 101, "eq", False),
        ("boolean", "true", "eq", False),
        ("boolean", True, "eq", True),
        ("label", "short", "eq", True),
    ],
)
async def test_where_enforces_declared_property_kind(kind, value, op, accepted):
    ctx = SuggestionContext(features=context().features, property_allowlist={catalog()[0].key: {"typed_prop": kind}})
    client = Client(
        {
            "suggestions": [
                {
                    "rule": demo_rule(
                        definition={
                            "event_keys": [catalog()[0].key],
                            "measure": "exists",
                            "where": {"prop": "typed_prop", "op": op, "value": value},
                        }
                    ),
                    "rationale": "test",
                }
            ]
        }
    )
    assert bool(await provider(client, ctx).suggest_rules(catalog())) is accepted


async def test_malformed_schema_extra_fields_and_oversized_output_are_rejected():
    for value in [
        demo_rule(unexpected="value"),
        demo_rule(
            definition={
                "event_keys": [catalog()[0].key],
                "measure": "count",
                "unknown": True,
            }
        ),
    ]:
        client = Client({"suggestions": [{"rule": value, "rationale": "test"}]})
        assert await provider(client).suggest_rules(catalog()) == []
    client = Client({"suggestions": [{"rule": demo_rule(), "rationale": "test"}] * 21})
    assert await provider(client).suggest_rules(catalog()) == []


async def test_no_property_schema_means_no_property_suggestions():
    client = Client(
        {
            "suggestions": [
                {
                    "rule": demo_rule(
                        definition={
                            "event_keys": [catalog()[0].key],
                            "measure": "last",
                            "value_prop": "tokens_left",
                        }
                    ),
                    "rationale": "test",
                }
            ]
        }
    )
    ctx = SuggestionContext(features=context().features)
    assert await provider(client, ctx).suggest_rules(catalog()) == []


async def test_provider_factory_failure_returns_safe_fallback():
    # Factory errors are still provider failures, even before the port method is reached.
    from feature_signal.services.rule_suggest_service import RuleSuggestService

    class Repo:
        async def list(self, app_id):
            return []

    def factory(context):
        raise RuntimeError("Provider unavailable")

    svc = RuleSuggestService(feature_repo=Repo(), event_repo=Repo(), rule_repo=Repo(), provider_factory=factory)
    assert await svc.suggest("app") == []
    assert (await svc.explain("app", ranking())).confidence == 0


async def test_paywall_preserves_original_factual_copy_and_does_not_add_absent_fields():
    client = Client({"title": "A new title", "subtitle": "A new subtitle"})
    assert await provider(client).paywall_copy("Creators", {"title": "Original"}) == {"title": "Original"}
    assert await provider(client).paywall_copy("Creators", {"title": "Export for $9"}) == {"title": "Export for $9"}


async def test_explanation_rejects_number_words_in_generated_hypothesis():
    client = Client(
        {"summary": "Any summary", "hypothesis": "This causes revenue to grow ten times", "confidence": 0.8}
    )
    result = await provider(client).explain(ranking(), catalog())
    assert result.confidence == 0
    assert "ten times" not in result.hypothesis


@pytest.mark.parametrize(
    "hypothesis",
    [
        "HD export causes revenue to increase; show this group the lifetime offer.",
        "HD export may predict intent; show the lifetime offer to this group.",
        "HD export may indicate demand; statistical confidence is extremely high.",
        "The evidence is conclusive and the result is guaranteed.",
        "Feature usage may reflect different user needs. Recommend a discounted offer.",
    ],
)
def test_explanation_rejects_unapproved_causal_offer_and_confidence_prose(hypothesis):
    from feature_signal.domain.models import Explanation
    from feature_signal.integrations.llm.schemas import fallback_explanation, safe_explanation

    value = ranking()
    result = safe_explanation(value, Explanation("discard", hypothesis, 0.99))
    assert result == fallback_explanation(value)


async def test_vetted_tentative_hypothesis_never_uses_model_confidence():
    client = Client(
        {
            "summary": "Discard this summary",
            "hypothesis": "Feature usage may reflect different user needs.",
            "confidence": 0.99,
        }
    )
    result = await provider(client).explain(ranking(), catalog())
    assert result.hypothesis == "Feature usage may reflect different user needs."
    assert result.confidence == 0.0


@pytest.mark.parametrize(
    "rationale",
    [
        "HD export causes revenue to increase; show this group the lifetime offer.",
        "Revenue will grow by 999 percent with certain statistical confidence.",
    ],
)
async def test_rule_rationale_is_rendered_from_validated_measure_instead_of_model_prose(rationale):
    client = Client({"suggestions": [{"rule": demo_rule(), "rationale": rationale}]})
    result = await provider(client).suggest_rules(catalog())
    assert len(result) == 1
    assert result[0][1] == (
        "Hypothesis: the 'exists' measure over declared events within 7 days may describe behavioral differences. "
        "Randomized arms must establish any offer effect."
    )

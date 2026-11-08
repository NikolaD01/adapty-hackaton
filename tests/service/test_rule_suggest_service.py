"""Service tests enforce validation even for non-OpenAI providers, with no persistence."""

import pytest

from feature_signal.domain.models import EventType, Explanation, Feature, Ranking, Rule, RuleDefinition
from feature_signal.services.rule_suggest_service import RuleSuggestService


class Repo:
    def __init__(self, items):
        self.items = items
        self.calls = []

    async def list(self, app_id):
        self.calls.append(app_id)
        return self.items

    async def save(self, *args):
        raise AssertionError("Suggestions must not be saved")


class Provider:
    model_name = "fake-provider"

    def __init__(self, suggestions=None, error=None):
        self.suggestions = suggestions or []
        self.error = error

    async def suggest_rules(self, catalog):
        if self.error:
            raise self.error
        return self.suggestions

    async def explain(self, ranking, catalog):
        if self.error:
            raise self.error
        return Explanation("Invented 999 revenue", "Feature usage may reflect different user needs.", 0.8)


def rule(key="hd_blocked_7d", feature="hd_export", definition=None):
    return Rule(
        key,
        "HD export blocked",
        "Blocked in the last seven days",
        definition or RuleDefinition(["pt_track_hd_export_blocked"], "exists", 7),
        "ai",
        feature,
    )


def service(provider=None, rules=(), **kwargs):
    return RuleSuggestService(
        feature_repo=Repo([Feature("hd_export", "HD export", "Export in HD")]),
        event_repo=Repo([EventType(1, "pt_track_hd_export_blocked", "Blocked export", "HD blocked", ["hd_export"])]),
        rule_repo=Repo(list(rules)),
        provider=provider,
        **kwargs,
    )


async def test_valid_demo_suggestion_returned_without_persistence_and_app_scoped():
    value = rule()
    svc = service(Provider([(value, "Demand hypothesis")]))
    assert await svc.suggest("app-one") == [
        (
            value,
            (
                "Hypothesis: the 'exists' measure over declared events within 7 days "
                "may describe behavioral differences. "
                "Randomized arms must establish any offer effect."
            ),
        )
    ]
    assert svc.model_name == "fake-provider"
    assert svc.feature_repo.calls == ["app-one"]
    assert svc.event_repo.calls == ["app-one"]
    assert svc.rule_repo.calls == ["app-one"]


@pytest.mark.parametrize(
    "candidate",
    [
        rule(feature="unknown"),
        rule(definition=RuleDefinition(["unknown"], "count")),
        rule(definition=RuleDefinition(["pt_track_hd_export_blocked"], "ratio")),
        rule(definition=RuleDefinition(["pt_track_hd_export_blocked"], "sum", value_prop="invented")),
        rule(key="BAD KEY"),
    ],
)
async def test_invalid_fake_provider_suggestion_is_rejected(candidate):
    assert await service(Provider([(candidate, "test")])).suggest("app") == []


async def test_duplicates_existing_and_batch_are_rejected():
    assert await service(Provider([(rule(), "test")]), rules=[rule(key="existing")]).suggest("app") == []
    assert len(await service(Provider([(rule(), "test"), (rule(key="other"), "test")])).suggest("app")) == 1


async def test_provider_failures_and_malformed_payload_fall_back():
    assert await service(Provider(error=RuntimeError("offline"))).suggest("app") == []
    assert await service(Provider([{"rule": "bad"}])).suggest("app") == []


async def test_factory_receives_fresh_feature_context_with_explicit_properties():
    contexts = []

    def factory(context):
        contexts.append(context)
        return Provider(
            [
                (
                    rule(definition=RuleDefinition(["pt_track_hd_export_blocked"], "last", value_prop="tokens_left")),
                    "Quota",
                )
            ]
        )

    svc = service(
        provider_factory=factory, property_allowlist={"pt_track_hd_export_blocked": {"tokens_left": "number"}}
    )
    assert len(await svc.suggest("app")) == 1
    assert contexts[0].features[0].key == "hd_export"
    assert svc.model_name == "fake-provider"
    svc.feature_repo.items = []
    assert await svc.suggest("other-app") == []
    assert contexts[1].features == ()


async def test_explain_keeps_numeric_summary_even_with_fake_provider():
    value = Ranking("hd_export", 2.5, "up", 1.7, 1.2, 2.1, 1.4, 200, 300, True)
    result = await service(Provider()).explain("app", value)
    assert "999" not in result.summary
    assert "1.7" in result.summary
    assert result.hypothesis == "Feature usage may reflect different user needs."
    fallback = await service(Provider(error=RuntimeError())).explain("app", value)
    assert fallback.confidence == 0


async def test_service_rejects_alternate_provider_causal_and_offer_claims():
    class UnsafeProvider(Provider):
        async def explain(self, ranking, catalog):
            return Explanation(
                "discard",
                "HD export causes revenue to increase; show this group the lifetime offer.",
                0.99,
            )

    value = Ranking("hd_export", 2.5, "up", 1.7, 1.2, 2.1, 1.4, 200, 300, True)
    result = await service(UnsafeProvider()).explain("app", value)
    assert result.hypothesis == "A behavioral hypothesis requires a randomized offer test."
    assert result.confidence == 0.0
    assert "1.7" in result.summary


async def test_service_replaces_alternate_provider_rationale_with_local_hypothesis():
    candidate = rule()
    svc = service(Provider([(candidate, "This causes revenue growth; publish the lifetime offer.")]))
    result = await svc.suggest("app")
    assert result == [
        (
            candidate,
            (
                "Hypothesis: the 'exists' measure over declared events within 7 days "
                "may describe behavioral differences. "
                "Randomized arms must establish any offer effect."
            ),
        )
    ]

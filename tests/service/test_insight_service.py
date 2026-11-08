from dataclasses import dataclass

import pandas as pd
import pytest

from feature_signal.domain.models import Explanation, FeatureMatrix, Rule, RuleDefinition
from feature_signal.services.insight_service import InsightService, InsightState, PublishedFlow
from tests.fakes import FakeProposalSink, FakeTierStore, FakeValueStore


@dataclass
class Dataset:
    count: int = 3000

    def users(self):
        return pd.DataFrame(
            {
                "user_id": [f"u{i:05d}" for i in range(self.count)],
                "install_at": ["2026-01-01T00:00:00Z"] * self.count,
                "edits": [i // 1000 for i in range(self.count)],
                "ab_test": ["Main: 3 plans vs lifetime anchor (NA)"] * self.count,
                "flow": ["main" if i % 2 == 0 else "main_lifetime" for i in range(self.count)],
                "platform": ["iOS"] * self.count,
            }
        )

    def transactions(self):
        return pd.DataFrame(
            {
                "user_id": [f"u{i:05d}" for i in range(self.count)],
                "purchased_at": ["2026-01-02T00:00:00Z"] * self.count,
                "price_usd": [2 + 8 * (i // 1000) + 3 * (i % 2) for i in range(self.count)],
                "refunded_at": [None] * self.count,
            }
        )


class Rules:
    async def list(self, app_id):
        return [Rule("edits", "Edits", "Edits count", RuleDefinition(["edit"], "count"), feature="editor")]


class Explainer:
    def __init__(self):
        self.calls = []

    async def explain(self, app_id, ranking):
        self.calls.append((app_id, ranking))
        return Explanation("Measured behavioral association.", "Hypothesis: engagement may differ.", 0.0)


def service(**kwargs):
    defaults = dict(
        dataset=Dataset(),
        as_of="2026-05-01T00:00:00Z",
        value_store=FakeValueStore(),
        tier_store=FakeTierStore(),
        proposal_sink=FakeProposalSink(),
        rule_repo=Rules(),
        offline_columns=["edits"],
        offline_features={"edits": "editor"},
        published_flows={
            "main_lifetime": PublishedFlow("flow-lifetime-id", "Lifetime", True, frozenset({"editor"})),
            "main": PublishedFlow("flow-main-id", "Main", True, frozenset({"editor"})),
        },
        state=InsightState(),
        user_id_map={f"u{i:05d}": f"u{i:05d}" for i in range(3000)},
        live_outcome_rules=frozenset({"edits", "new_metric"}),
    )
    defaults.update(kwargs)
    return InsightService(**defaults)


async def test_the_outcome_window_setting_reaches_the_drafts_and_the_reason_text():
    svc = service(window_days=30, dataset=Dataset())
    await svc.run("app", "offline")
    assert svc.proposal_sink.created
    for draft in svc.proposal_sink.created:
        assert draft.evidence["outcome_window_days"] == 30
        assert "over 30 days" in draft.reason


async def test_offline_run_reports_tiers_without_storing_them_and_hands_drafts_to_sink():
    explainer = Explainer()
    svc = service(explainer=explainer)
    result = await svc.run("app", "offline")
    assert result.source == "offline"
    assert result.rankings and any(item.passed for item in result.rankings)
    assert result.tiers and result.segments and result.uplift
    assert await svc.tier_store.list("app") == []  # only a live run may write tiers (they become Adapty attributes)
    assert svc.proposal_sink.created
    for draft in svc.proposal_sink.created:
        assert draft.condition.field == "p_segment"
        assert draft.condition.value == [draft.segment_key]
        assert draft.flow_id == "flow-lifetime-id"
        assert draft.ci_low > 0
        assert draft.highlight_feature == "editor"
        assert "refund" in draft.reason.lower()
        assert "synthetic" in draft.reason.lower()
        assert "Hypothesis:" in draft.reason
        assert draft.evidence["outcome_window_days"] == 90
        assert draft.evidence["segment_conditions"]
        assert draft.evidence["refunds"]
        assert draft.adapty_filters
    assert explainer.calls
    assert svc.latest("app").run_id == result.run_id
    assert svc.latest("other") is None
    result.rankings.clear()
    assert svc.latest("app").rankings


async def test_unpublished_or_unknown_flow_never_becomes_executable_draft():
    svc = service(published_flows={"main_lifetime": PublishedFlow("draft-id", "Draft", False)})
    result = await svc.run("app", "offline")
    assert result.uplift
    assert svc.proposal_sink.created == []


async def test_empty_cohort_clears_tiers_without_fabricated_proposal():
    svc = service(as_of="2026-01-02T00:00:00Z")
    result = await svc.run("app", "offline")
    assert result.rankings == result.tiers == result.segments == result.uplift == []
    assert svc.proposal_sink.created == []


async def test_sink_failure_does_not_publish_successful_latest_run():
    class BrokenSink:
        async def create_many(self, app_id, drafts):
            raise RuntimeError("storage unavailable")

    svc = service(proposal_sink=BrokenSink())
    with pytest.raises(RuntimeError, match="storage unavailable"):
        await svc.run("app", "offline")
    assert svc.latest("app") is None


async def test_live_values_join_known_users_and_leave_unmeasured_rules_as_hypotheses():
    class Matrix:
        async def matrix(self, app_id):
            return FeatureMatrix(
                [f"u{i:05d}" for i in range(3000)],
                ["edits", "new_metric"],
                [[i // 1000, float("nan")] for i in range(3000)],
            )

    svc = service(value_store=Matrix())
    result = await svc.run("app", "live")
    assert result.source == "live"
    assert any(item.feature == "edits" and item.passed for item in result.rankings)
    assert result.hypotheses == ["new_metric"]
    assert all(item.rule_key != "new_metric" for item in result.tiers)


async def test_unjoined_live_values_fall_back_without_relabeling_offline_rules():
    values = FakeValueStore()
    await values.put_many("app", "edits_7d", {"new-live-user": 20})
    svc = service(value_store=values)
    result = await svc.run("app", "live")
    assert result.source == "offline"
    assert result.hypotheses == ["edits_7d"]
    assert all(item.feature == "edits" for item in result.rankings)
    assert all(item.rule_key != "edits_7d" for item in result.tiers)


async def test_small_live_cohort_does_not_lower_minimum_group_size():
    values = FakeValueStore()
    await values.put_many("app", "edits", {f"u{i:05d}": float(i % 3) for i in range(200)})
    result = await service(value_store=values).run("app", "live")
    assert result.source == "live"
    assert not any(item.passed for item in result.rankings)
    assert not result.tiers


async def test_explicit_id_mapping_does_not_join_unmapped_live_copies():
    values = FakeValueStore()
    await values.put_many("app", "edits", {"historic-42": 2, "live-copy-42": 999})
    svc = service(value_store=values, user_id_map={"historic-42": "u00042"})
    result = await svc.run("app", "live")
    assert result.source == "live"
    assert not any(item.passed for item in result.rankings)


async def test_bad_source_is_rejected_before_any_side_effect():
    svc = service()
    with pytest.raises(ValueError, match="source"):
        await svc.run("app", "wrong")
    assert svc.latest("app") is None


async def test_finite_current_only_rule_is_a_hypothesis_even_for_known_historical_ids():
    class CurrentRules:
        async def list(self, app_id):
            return [
                Rule(
                    "new_7d",
                    "New behavior",
                    "Recent behavior",
                    RuleDefinition(["recent"], "count", window_days=7),
                    feature="editor",
                )
            ]

    values = FakeValueStore()
    await values.put_many("app", "new_7d", {f"u{i:05d}": float(i // 1000) for i in range(3000)})
    svc = service(value_store=values, rule_repo=CurrentRules(), offline_features={})
    result = await svc.run("app", "live")
    assert result.source == "offline"
    assert result.hypotheses == ["new_7d"]
    assert not any(item.feature == "new_7d" for item in result.rankings)
    assert not result.tiers and not svc.proposal_sink.created


async def test_coincidental_id_match_without_verified_identity_map_does_not_join():
    values = FakeValueStore()
    await values.put_many("app", "edits", {f"u{i:05d}": float(i // 1000) for i in range(3000)})
    result = await service(value_store=values, user_id_map={}).run("app", "live")
    assert result.source == "offline"
    assert "edits" in result.hypotheses


async def test_draft_conditions_fit_existing_proposal_wire_contract():
    from dataclasses import asdict

    from feature_signal.schemas.proposals import AdaptyFilter, ProposalCondition

    svc = service()
    await svc.run("app", "offline")
    assert svc.proposal_sink.created
    for draft in svc.proposal_sink.created:
        ProposalCondition(attribute=draft.condition.field, op=draft.condition.op, value=draft.condition.value)
        for condition in draft.adapty_filters:
            AdaptyFilter.model_validate(asdict(condition))


async def test_offline_fallback_does_not_rank_a_name_colliding_with_unverified_live_rule():
    values = FakeValueStore()
    await values.put_many("app", "edits", {"unknown-user": 5})
    result = await service(value_store=values).run("app", "live")
    assert result.source == "offline"
    assert "edits" in result.hypotheses
    assert set(result.hypotheses).isdisjoint(item.feature for item in result.rankings)
    assert set(result.hypotheses).isdisjoint(item.rule_key for item in result.tiers)


async def test_membership_evidence_contains_only_behavioral_predicates():
    svc = service()
    await svc.run("app", "offline")
    assert svc.proposal_sink.created
    for draft in svc.proposal_sink.created:
        assert draft.evidence["segment_conditions"]
        assert all(item["field"] == "edits" for item in draft.evidence["segment_conditions"])
        assert any(item["field"] == "platform" for item in draft.evidence["analysis_conditions"])
        assert any(item.field == "platform" for item in draft.adapty_filters)


async def test_offline_run_never_clears_tiers_from_a_live_run():
    from feature_signal.domain.models import FeatureTier

    svc = service()
    live_tier = FeatureTier(feature="editor", rule_key="edits_7d", low_max=1, mid_max=4, passed=True)
    await svc.tier_store.put_many("app", [live_tier])
    await svc.run("app", "offline")
    assert await svc.tier_store.list("app") == [live_tier]

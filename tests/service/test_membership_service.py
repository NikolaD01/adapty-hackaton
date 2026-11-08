"""C9: the fast loop writes only what changed. Fake ports, no network, no database."""

import asyncio
from types import SimpleNamespace

import pytest

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import FeatureTier
from feature_signal.services.membership_service import MembershipService, segment_matches
from tests.fakes import FakeAttributeWriter, FakeTierStore, FakeValueStore

APP = "app1"


class FakeState:
    """What C last wrote per user (the `adapty_attribute_state` table)."""

    def __init__(self) -> None:
        self.data: dict[str, dict] = {}

    async def get_many(self, app_id, ids):
        return {u: dict(self.data[u]) for u in ids if u in self.data}

    async def put(self, app_id, customer_user_id, attributes):
        self.data[customer_user_id] = dict(attributes)


class FakeProposals:
    def __init__(self, *proposals) -> None:
        self.items = list(proposals)

    async def list(self, app_id, status=None):
        return [p for p in self.items if status is None or p.status == status]


def proposal(key, conditions, status="live"):
    return SimpleNamespace(status=status, segment_key=key, evidence={"segment_conditions": conditions})


AI_TIER = FeatureTier(feature="ai_generate", rule_key="ai_uses_7d", low_max=2, mid_max=7, passed=True)
POWER = proposal(
    "power_editor",
    [{"field": "f_ai_generate_tier", "op": "IN", "value": ["high"]}, {"field": "edits_1d", "op": ">=", "value": 5}],
)


async def build(values=None, tiers=(AI_TIER,), proposals=(POWER,), state=None, writer=None, **kwargs):
    value_store, tier_store = FakeValueStore(), FakeTierStore()
    for rule_key, per_user in (values or {}).items():
        await value_store.put_many(APP, rule_key, per_user)
    await tier_store.put_many(APP, list(tiers))
    state = state if state is not None else FakeState()
    writer = writer if writer is not None else FakeAttributeWriter()
    service = MembershipService(value_store, tier_store, FakeProposals(*proposals), state, writer, **kwargs)
    return service, writer, state


VALUES = {"ai_uses_7d": {"u1": 9.0, "u2": 1.0}, "edits_1d": {"u1": 6.0, "u2": 0.0}}


async def test_first_sync_writes_tier_and_segment():
    service, writer, _ = await build(VALUES)
    result = await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"f_ai_generate_tier": "high", "p_segment": "power_editor"})]
    assert (result.checked, result.changed, result.attributes_written) == (1, 1, 2)


async def test_unchanged_user_writes_nothing():
    service, writer, _ = await build(VALUES)
    await service.sync_users(APP, ["u1"])
    writer.writes.clear()
    result = await service.sync_users(APP, ["u1"])
    assert writer.writes == []
    assert (result.checked, result.changed, result.attributes_written) == (1, 0, 0)


async def test_user_crossing_a_tier_writes_one_key():
    service, writer, _ = await build({"ai_uses_7d": {"u2": 1.0}, "edits_1d": {"u2": 0.0}})
    await service.sync_users(APP, ["u2"])
    assert writer.writes == [("u2", {"f_ai_generate_tier": "low"})]
    writer.writes.clear()
    await service._values.put_many(APP, "ai_uses_7d", {"u2": 4.0})
    result = await service.sync_users(APP, ["u2"])
    assert writer.writes == [("u2", {"f_ai_generate_tier": "mid"})]
    assert result.attributes_written == 1


async def test_user_leaving_the_segment_gets_p_segment_null():
    service, writer, _ = await build(VALUES)
    await service.sync_users(APP, ["u1"])
    writer.writes.clear()
    await service._values.put_many(APP, "edits_1d", {"u1": 1.0})  # no longer 5+ edits
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": None})]


async def test_a_tier_that_disappears_is_deleted():
    service, writer, _ = await build(VALUES, proposals=())
    await service.sync_users(APP, ["u1"])
    writer.writes.clear()
    await service._tiers.put_many(APP, [])  # no passed tiers any more
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"f_ai_generate_tier": None})]


async def test_only_passed_tiers_are_written_and_at_most_ten():
    tiers = [FeatureTier(f"feat{i:02d}", f"r{i}", 1, 2, passed=True) for i in range(12)]
    tiers.append(FeatureTier("failed", "rf", 1, 2, passed=False))
    values = {t.rule_key: {"u1": 5.0} for t in tiers}
    service, writer, _ = await build(values, tiers=tiers, proposals=())
    await service.sync_users(APP, ["u1"])
    ((_, written),) = writer.writes
    assert len(written) == 10
    assert "f_failed_tier" not in written
    assert all(k.startswith("f_feat") for k in written)


async def test_the_first_matching_live_proposal_wins_and_other_statuses_are_ignored():
    always = [{"field": "edits_1d", "op": ">=", "value": 0}]
    other_rule = [{"field": "edits_1d", "op": ">=", "value": 1}]  # a draft with a DIFFERENT rule never matters
    proposals = [
        proposal("draft_one", other_rule, status="draft"),
        proposal("second", always),
        proposal("third", always),
    ]
    service, writer, _ = await build({"edits_1d": {"u1": 3.0}}, tiers=(), proposals=proposals)
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": "second"})]


async def test_a_proposal_being_activated_already_counts():
    always = [{"field": "edits_1d", "op": ">=", "value": 0}]
    for status, expected in (("executing", "p"), ("awaiting_publish", "p"), ("approved", None), ("failed", None)):
        service, writer, _ = await build(
            {"edits_1d": {"u1": 3.0}}, tiers=(), proposals=[proposal("p", always, status=status)]
        )
        await service.sync_users(APP, ["u1"])
        assert writer.writes == ([("u1", {"p_segment": "p"})] if expected else []), status


async def test_proposals_with_the_same_behaviour_share_the_first_segment_key():
    rule = [{"field": "edits_1d", "op": ">=", "value": 5}]
    props = [proposal("ios_key", rule), proposal("android_key", rule)]  # same behaviour, split later by platform
    service, writer, _ = await build({"edits_1d": {"u1": 6.0}}, tiers=(), proposals=props)
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": "ios_key"})]


async def test_an_earlier_draft_with_the_same_behaviour_decides_the_shared_key():
    rule = [{"field": "edits_1d", "op": ">=", "value": 5}]
    props = [proposal("first_draft", rule, status="draft"), proposal("later_live", rule)]
    service, writer, _ = await build({"edits_1d": {"u1": 6.0}}, tiers=(), proposals=props)
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": "first_draft"})]  # activating the draft later must not re-key users


async def test_a_rejected_or_failed_proposal_does_not_decide_the_shared_key():
    rule = [{"field": "edits_1d", "op": ">=", "value": 5}]
    props = [
        proposal("rejected_one", rule, status="rejected"),
        proposal("failed_one", rule, status="failed"),
        proposal("real", rule),
    ]
    service, writer, _ = await build({"edits_1d": {"u1": 6.0}}, tiers=(), proposals=props)
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": "real"})]


async def test_different_behaviour_keeps_its_own_key():
    props = [
        proposal("many", [{"field": "edits_1d", "op": ">=", "value": 5}]),
        proposal("few", [{"field": "edits_1d", "op": "<", "value": 5}]),
    ]
    service, writer, _ = await build({"edits_1d": {"u1": 6.0, "u2": 1.0}}, tiers=(), proposals=props)
    await service.sync_users(APP, ["u1", "u2"])
    assert dict(writer.writes) == {"u1": {"p_segment": "many"}, "u2": {"p_segment": "few"}}


async def test_none_means_every_user_with_values():
    service, writer, _ = await build(VALUES)
    result = await service.sync_users(APP, None)
    assert {u for u, _ in writer.writes} == {"u1", "u2"}
    assert result.checked == 2


async def test_a_user_without_values_gets_no_attributes():
    service, writer, _ = await build(VALUES)
    result = await service.sync_users(APP, ["ghost"])
    assert writer.writes == []
    assert (result.checked, result.changed) == (1, 0)


async def test_a_proposal_without_segment_conditions_matches_nobody():
    bare = SimpleNamespace(status="live", segment_key="x", evidence={})
    service, writer, _ = await build(VALUES, tiers=(), proposals=(bare,))
    await service.sync_users(APP, ["u1"])
    assert writer.writes == []


async def test_concurrency_is_limited():
    running = peak = 0

    class SlowWriter:
        async def write(self, customer_user_id, attributes):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1

    values = {"ai_uses_7d": {f"u{i}": 9.0 for i in range(20)}}
    service, _, _ = await build(values, proposals=(), writer=SlowWriter(), concurrency=3)
    await service.sync_users(APP, None)
    assert peak == 3


async def test_a_failed_write_is_not_recorded_so_it_is_retried_and_others_still_go_through():
    class Flaky:
        def __init__(self):
            self.writes = []

        async def write(self, customer_user_id, attributes):
            if customer_user_id == "u2":
                raise ApiError(502, "adapty_unavailable", "down")
            self.writes.append(customer_user_id)

    service, _, state = await build(VALUES, writer=Flaky())
    with pytest.raises(ApiError) as caught:
        await service.sync_users(APP, ["u1", "u2"])
    assert caught.value.code == "membership_sync_partial"
    assert caught.value.details["failed"] == 1
    assert "u1" in state.data
    assert "u2" not in state.data


def test_segment_matches_numbers_tiers_and_missing_fields():
    values, tiers = {"edits": 6.0}, {"f_x_tier": "high"}
    assert segment_matches([{"field": "edits", "op": ">=", "value": 5}], values, tiers)
    assert not segment_matches([{"field": "edits", "op": "<", "value": 5}], values, tiers)
    assert segment_matches([{"field": "f_x_tier", "op": "IN", "value": ["mid", "high"]}], values, tiers)
    assert segment_matches([{"field": "f_x_tier", "op": "NOT IN", "value": ["low"]}], values, tiers)
    assert not segment_matches([{"field": "missing", "op": ">=", "value": 0}], values, tiers)
    assert not segment_matches([], values, tiers)  # no conditions = matches nobody
    assert segment_matches([{"field": "edits", "op": "=", "value": 6}], values, tiers)  # B may write "=" / "=="
    assert segment_matches([{"field": "f_x_tier", "op": "==", "value": "high"}], values, tiers)
    assert not segment_matches([{"field": "edits", "op": "!=", "value": 6}], values, tiers)


async def test_failed_sync_keeps_the_actionable_cause_without_exposing_raw_details():
    class MissingProfiles:
        async def write(self, user, attributes):
            raise ApiError(
                502,
                "adapty_profile_missing",
                "The profile does not exist in the configured Adapty app. Seed demo profiles first.",
                {"body": "private upstream details"},
            )

    service, _, _ = await build(VALUES, writer=MissingProfiles())
    with pytest.raises(ApiError) as caught:
        await service.sync_users(APP, None)
    assert caught.value.code == "membership_sync_partial"
    assert "configured Adapty app" in caught.value.message
    assert "the rest were" not in caught.value.message
    assert caught.value.details["causes"] == {"adapty_profile_missing": 2}
    assert "private upstream details" not in repr(caught.value.details)


def activated(key, conditions, value, status="live"):
    return SimpleNamespace(
        status=status,
        segment_key=key,
        evidence={"segment_conditions": conditions},
        condition=SimpleNamespace(value=value),
    )


async def test_rejecting_an_earlier_draft_does_not_re_key_an_activated_segment():
    rule = [{"field": "edits_1d", "op": ">=", "value": 5}]
    # Android was activated while the iOS draft decided the shared key; the iOS draft is rejected afterwards.
    props = [proposal("ios_key", rule, status="rejected"), activated("android_key", rule, ["ios_key"])]
    service, writer, _ = await build({"edits_1d": {"u1": 6.0}}, tiers=(), proposals=props)
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": "ios_key"})]  # still what the live Adapty segment filters on


async def test_a_human_edited_value_on_an_activated_proposal_is_what_sync_writes():
    rule = [{"field": "edits_1d", "op": ">=", "value": 5}]
    props = [activated("power_editor", rule, ["heavy"])]
    service, writer, _ = await build({"edits_1d": {"u1": 6.0}}, tiers=(), proposals=props)
    await service.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": "heavy"})]


async def test_later_drafts_share_the_frozen_key_of_an_activated_proposal():
    rule = [{"field": "edits_1d", "op": ">=", "value": 5}]
    from feature_signal.services.membership_service import canonical_segment_keys

    keys = canonical_segment_keys(
        [proposal("old_draft", rule, status="draft"), activated("live_one", rule, ["frozen"])]
    )
    assert keys == {"live_one": "frozen", "old_draft": "frozen"}

"""C4: approve runs the whole Adapty sequence. Fake CLI and fake membership sync, real SQLite, no network."""

import pytest

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import SyncResult
from feature_signal.integrations.adapty.cli import AdaptyCommands
from feature_signal.repositories.decisions import DecisionRepository
from feature_signal.schemas.proposals import AppSettings, ProposalIn
from feature_signal.services.activation_service import ActivationService
from feature_signal.services.membership_service import canonical_segment_keys
from feature_signal.services.proposal_service import ProposalService
from tests.integration.adapty_helpers import make_factory

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
ADAPTY = "9ccde368-e282-4385-a260-18b428560ba5"

PLACEMENT = {
    "id": "pl1",
    "developer_id": "main",
    "title": "Main paywall",
    "audiences": [
        {"content_type": "flow_ab_test", "segment_ids": ["na"], "ab_test_id": "t9", "priority": 0},
        {"content_type": "flow", "segment_ids": [], "flow_id": "f-default", "priority": 1},
    ],
}


def proposal_input(**over):
    base = {
        "trigger_placement": "main",
        "segment_key": "power_editor",
        "condition": {"attribute": "p_segment", "op": "IN", "value": ["power_editor"]},
        "adapty_filters": [{"field": "subscription_state", "op": "IN", "value": ["never_subscribed"]}],
        "action": {"flow_id": "f-lifetime", "flow_name": "Lifetime", "needs_publish": False},
        "holdout_pct": 20,
        "expected_effect": {"diff": 14.4, "ci_low": 9.1, "ci_high": 19.8},
        "reason": "r",
    }
    base.update(over)
    return ProposalIn.model_validate(base)


class World:
    """Everything the service talks to, with one shared call log so the ORDER can be asserted."""

    def __init__(self, *, segments=None, flow_status="published", fail=None):
        self.log: list[str] = []
        self.cli_calls: list[tuple[str, ...]] = []
        self.segments = segments or []
        self.flow_status = flow_status
        self.fail = fail  # command words that raise
        self.sync_result = SyncResult(checked=3, changed=2, attributes_written=4)
        self.ab_test = {
            "flows": [
                {"flow_id": "f-default", "title": "A", "weight": 50},
                {"flow_id": "f-lifetime", "title": "B", "weight": 50},
            ]
        }

    async def run(self, *args):
        self.cli_calls.append(args)
        command = " ".join(args[:2])
        self.log.append(command)
        if self.fail == command:
            raise ApiError(502, "adapty_cli_failed", f"{command} failed", {"stderr": "boom"})
        if command == "segments list":
            return {"data": self.segments}
        if command == "segments create":
            return {"id": "seg1", "title": args[args.index("--title") + 1]}
        if command == "segments update":
            return {"id": args[2]}
        if command == "placements list":
            return {"data": [{"id": "pl1", "developer_id": "main"}]}
        if command == "placements get":
            return PLACEMENT
        if command == "ab-tests create":
            return {"ab_test_id": "t1", "state": "draft"}
        if command == "ab-tests get":
            return self.ab_test
        if command == "flows get":
            return {"id": args[2], "status": self.flow_status}
        return {}

    async def sync_users(self, app_id, ids):
        self.log.append("sync")
        if self.fail == "sync":
            raise ApiError(502, "membership_sync_partial", "Could not sync all profiles")
        self.sync_ids = ids
        return self.sync_result


@pytest.fixture
def factory(db_url):
    return make_factory(db_url)


async def run_approve(factory, world, item=None, decided_by="human", mode=None):
    async with factory() as s:
        service = ProposalService(s)
        if mode:
            await service.put_settings(APP, AppSettings(mode=mode))
        (created,) = await service.create(APP, [item or proposal_input()])
    async with factory() as s:
        activation = ActivationService(s, AdaptyCommands(world, ADAPTY), world)
        out = await activation.approve(created.proposal_id, decided_by=decided_by)
    return out, created.proposal_id


async def decisions(factory):
    async with factory() as s:
        return await DecisionRepository(s).list(APP)


def arg(call, flag):
    return call[call.index(flag) + 1]


async def test_the_steps_run_in_the_contract_order(factory):
    world = World()
    out, _ = await run_approve(factory, world)
    assert world.log == [
        "sync",
        "segments list",
        "segments create",
        "placements list",
        "placements get",
        "ab-tests create",
        "ab-tests start",
    ]
    assert world.sync_ids is None  # every user with values
    assert out.status == "live"


async def test_status_refs_actor_mode_and_decision_log(factory):
    world = World()
    out, pid = await run_approve(factory, world)
    assert (out.status, out.decided_by, out.mode_at_decision) == ("live", "human", "human")
    assert out.adapty.model_dump() == {
        "segment_id": "seg1",
        "placement_id": "pl1",
        "ab_test_id": "t1",
        "attributes_written": 4,
    }
    (decision,) = await decisions(factory)
    assert (decision.proposal_id, decision.decided_by, decision.action) == (pid, "human", "approve")
    assert [(s["step"], s["ok"]) for s in decision.steps] == [
        ("write_attributes", True),
        ("segments_create", True),
        ("placement_read", True),
        ("ab_tests_create", True),
        ("ab_tests_start", True),
    ]
    assert decision.steps[0]["detail"] == {"profiles": 2, "attributes_written": 4}
    assert decision.steps[1]["detail"] == {"segment_id": "seg1", "reused": False}


async def test_segment_filters_are_p_segment_and_the_adapty_filters(factory):
    world = World()
    await run_approve(factory, world)
    create = next(c for c in world.cli_calls if c[:2] == ("segments", "create"))
    assert arg(create, "--title") == "[fs] power_editor"
    assert [create[i + 1] for i, a in enumerate(create) if a == "--filter"] == [
        "attributes__p_segment@string:IN:power_editor",
        "subscription_state:IN:never_subscribed",
    ]


RULE = [{"field": "edits_1d", "op": ">=", "value": 5}]


async def test_segments_with_the_same_behaviour_filter_on_one_shared_p_segment_key(factory):
    """iOS and Android variants differ only by a native filter, so both must filter on the first one's key."""
    ios = proposal_input(
        segment_key="ios_key",
        condition={"attribute": "p_segment", "op": "IN", "value": ["ios_key"]},
        evidence={"segment_conditions": RULE},
    )
    android = proposal_input(
        segment_key="android_key",
        condition={"attribute": "p_segment", "op": "IN", "value": ["android_key"]},
        evidence={"segment_conditions": RULE},
        adapty_filters=[{"field": "platform", "op": "IN", "value": ["Android"]}],
    )
    async with factory() as s:
        await ProposalService(s).create(APP, [ios, android])
        ids = {p.segment_key: p.proposal_id for p in await ProposalService(s).list(APP)}
    world = World()
    async with factory() as s:
        await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(ids["android_key"])
    create = next(c for c in world.cli_calls if c[:2] == ("segments", "create"))
    assert arg(create, "--title") == "[fs] android_key"
    assert [create[i + 1] for i, a in enumerate(create) if a == "--filter"] == [
        "attributes__p_segment@string:IN:ios_key",
        "platform:IN:Android",
    ]
    # The key is frozen on the activated proposal: rejecting the iOS draft later must not re-key its users.
    async with factory() as s:
        stored = {p.segment_key: p for p in await ProposalService(s).list(APP)}
    assert stored["android_key"].condition.value == ["ios_key"]
    async with factory() as s:
        await ProposalService(s).reject(ids["ios_key"], "not now")
    async with factory() as s:
        keys = canonical_segment_keys(await ProposalService(s).list(APP))
    assert keys["android_key"] == "ios_key"


async def test_a_human_edited_condition_value_is_what_the_segment_targets(factory):
    async with factory() as s:
        (created,) = await ProposalService(s).create(APP, [proposal_input()])
    from feature_signal.schemas.proposals import ProposalPatch

    async with factory() as s:
        await ProposalService(s).patch(created.proposal_id, ProposalPatch(condition_value=["power_editor", "heavy"]))
    world = World()
    async with factory() as s:
        await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(created.proposal_id)
    create = next(c for c in world.cli_calls if c[:2] == ("segments", "create"))
    assert "attributes__p_segment@string:IN:power_editor,heavy" in create


async def test_ab_test_has_the_default_flow_as_control_and_the_offer_on_the_segment(factory):
    world = World()
    await run_approve(factory, world)
    import json

    create = next(c for c in world.cli_calls if c[:2] == ("ab-tests", "create"))
    assert arg(create, "--placement") == "pl1"
    assert arg(create, "--segment") == "seg1"
    assert json.loads(arg(create, "--flows")) == [
        {"flow_id": "f-default", "weight": 20, "title": "control"},
        {"flow_id": "f-lifetime", "weight": 80, "title": "offer"},
    ]
    start = next(c for c in world.cli_calls if c[:2] == ("ab-tests", "start"))
    assert start[2] == "t1"
    assert arg(start, "--placement") == "pl1"
    assert arg(start, "--segment") == "seg1"


async def test_an_existing_segment_is_reused_not_duplicated(factory):
    world = World(segments=[{"id": "seg9", "title": "[fs] power_editor"}])
    out, _ = await run_approve(factory, world)
    assert "segments create" not in world.log
    assert "segments update" in world.log
    assert out.adapty.segment_id == "seg9"
    create = next(c for c in world.cli_calls if c[:2] == ("ab-tests", "create"))
    assert arg(create, "--segment") == "seg9"
    (decision,) = await decisions(factory)
    assert decision.steps[1]["detail"] == {"segment_id": "seg9", "reused": True}


async def test_a_new_draft_flow_stops_at_awaiting_publish_before_the_ab_test(factory):
    world = World(flow_status="draft")
    item = proposal_input(action={"flow_id": "f-new", "flow_name": "AI paywall", "needs_publish": True})
    out, _ = await run_approve(factory, world, item)
    assert out.status == "awaiting_publish"
    assert world.log == ["sync", "segments list", "segments create"]
    (decision,) = await decisions(factory)
    assert decision.steps[-1]["step"] == "awaiting_publish"


async def test_after_the_human_publishes_approve_continues_to_live(factory):
    world = World(flow_status="draft")
    item = proposal_input(action={"flow_id": "f-new", "needs_publish": True})
    out, pid = await run_approve(factory, world, item)
    assert out.status == "awaiting_publish"

    world.flow_status = "published"
    world.log.clear()
    async with factory() as s:
        resumed = await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(pid)
    assert resumed.status == "live"
    assert world.log == ["flows get", "placements list", "placements get", "ab-tests create", "ab-tests start"]
    assert resumed.adapty.ab_test_id == "t1"
    assert resumed.adapty.segment_id == "seg1"  # kept from the first run


async def test_approve_before_the_flow_is_published_is_a_409_and_changes_nothing(factory):
    world = World(flow_status="draft")
    item = proposal_input(action={"flow_id": "f-new", "needs_publish": True})
    _, pid = await run_approve(factory, world, item)
    async with factory() as s:
        with pytest.raises(ApiError) as caught:
            await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(pid)
    assert (caught.value.status, caught.value.code) == (409, "flow_not_published")
    async with factory() as s:
        (still,) = await ProposalService(s).list(APP, "awaiting_publish")
    assert still.proposal_id == pid


async def test_a_failing_step_marks_failed_logs_the_error_and_stops(factory):
    world = World(fail="segments create")
    out, _ = await run_approve(factory, world)
    assert out.status == "failed"
    assert "ab-tests create" not in world.log
    (decision,) = await decisions(factory)
    failed = decision.steps[-1]
    assert (failed["step"], failed["ok"]) == ("segments_create", False)
    assert failed["detail"]["code"] == "adapty_cli_failed"
    assert [s["ok"] for s in decision.steps] == [True, False]


@pytest.mark.parametrize(
    ("command", "step"),
    [
        ("sync", "write_attributes"),
        ("segments list", "segments_create"),
        ("segments create", "segments_create"),
        ("placements list", "placement_read"),
        ("placements get", "placement_read"),
        ("ab-tests create", "ab_tests_create"),
        ("ab-tests start", "ab_tests_start"),
    ],
)
async def test_each_upstream_failure_is_logged_and_stops_activation(factory, command, step):
    world = World(fail=command)
    out, _ = await run_approve(factory, world)
    assert out.status == "failed"
    (decision,) = await decisions(factory)
    assert decision.steps[-1]["step"] == step
    assert decision.steps[-1]["ok"] is False
    assert decision.steps[-1]["detail"]["message"]
    assert world.log[-1] == command


async def test_the_secret_free_error_text_is_what_gets_logged(factory):
    world = World(fail="ab-tests start")
    out, _ = await run_approve(factory, world)
    assert out.status == "failed"
    (decision,) = await decisions(factory)
    assert decision.steps[-1]["step"] == "ab_tests_start"
    assert set(decision.steps[-1]["detail"]) == {"code", "message"}


async def test_an_offer_equal_to_the_control_fails_clearly(factory):
    world = World()
    item = proposal_input(action={"flow_id": "f-default", "needs_publish": False})
    out, _ = await run_approve(factory, world, item)
    assert out.status == "failed"
    (decision,) = await decisions(factory)
    assert decision.steps[-1]["detail"]["code"] == "offer_equals_control"
    assert "ab-tests create" not in world.log


async def test_a_placement_whose_default_is_not_a_flow_or_flow_test_fails(factory, monkeypatch):
    monkeypatch.setitem(PLACEMENT, "audiences", [{"content_type": "paywall", "segment_ids": [], "paywall_id": "x"}])
    world = World()
    out, _ = await run_approve(factory, world)
    assert out.status == "failed"
    (decision,) = await decisions(factory)
    assert decision.steps[-1]["detail"]["code"] == "placement_default_not_a_flow"


async def test_default_ab_test_uses_the_other_arm_without_replacing_the_default(factory, monkeypatch):
    monkeypatch.setitem(
        PLACEMENT, "audiences", [{"content_type": "flow_ab_test", "segment_ids": [], "ab_test_id": "existing"}]
    )
    world = World()
    out, _ = await run_approve(factory, world)
    assert out.status == "live"
    (decision,) = await decisions(factory)
    assert decision.steps[2]["detail"]["control_flow_id"] == "f-default"
    assert ("ab-tests", "get", "existing", "--app", ADAPTY) in world.cli_calls
    assert "placements update" not in world.log
    assert "ab-tests stop" not in world.log


async def test_default_ab_test_refuses_an_ambiguous_control(factory, monkeypatch):
    monkeypatch.setitem(
        PLACEMENT, "audiences", [{"content_type": "flow_ab_test", "segment_ids": [], "ab_test_id": "existing"}]
    )
    world = World()
    world.ab_test["flows"].append({"flow_id": "f-third", "weight": 10})
    out, _ = await run_approve(factory, world)
    assert out.status == "failed"
    (decision,) = await decisions(factory)
    assert decision.steps[-1]["detail"]["code"] == "placement_control_ambiguous"
    assert "ab-tests create" not in world.log


@pytest.mark.parametrize("base_source", ["evidence", "edit"])
async def test_published_ai_copy_uses_its_existing_base_arm_as_control(factory, monkeypatch, base_source):
    monkeypatch.setitem(
        PLACEMENT, "audiences", [{"content_type": "flow_ab_test", "segment_ids": [], "ab_test_id": "existing"}]
    )
    world = World()
    item = proposal_input(
        action={"flow_id": "f-copy", "needs_publish": True},
        evidence={"ai_copy": {"base_flow_id": "f-lifetime"}} if base_source == "evidence" else {},
    )
    out, pid = await run_approve(factory, world, item)
    assert out.status == "awaiting_publish"
    async with factory() as s:
        if base_source == "edit":
            row = await ProposalService(s)._get(pid)
            row.edits = [{"field": "flow_id", "from": "f-lifetime", "to": "f-copy", "at": row.created_at.isoformat()}]
            await s.commit()
        out = await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(pid)
    assert out.status == "live"
    latest = (await decisions(factory))[0]
    assert latest.steps[0]["detail"]["control_flow_id"] == "f-lifetime"


async def test_retry_before_test_creation_reuses_the_segment_and_preserves_history(factory):
    world = World(fail="placements get")
    out, pid = await run_approve(factory, world)
    assert out.status == "failed"
    world.fail = None
    world.segments = [{"id": "seg1", "title": "[fs] power_editor"}]
    async with factory() as s:
        out = await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(pid)
    assert out.status == "live"
    assert world.log.count("segments create") == 1
    assert world.log.count("ab-tests create") == 1
    assert len(await decisions(factory)) == 2


async def test_retry_does_not_replace_an_equivalent_live_proposal(factory):
    world = World(fail="placements get")
    _, failed_id = await run_approve(factory, world)
    world.fail = None
    live, _ = await run_approve(factory, world)
    world.log.clear()
    async with factory() as s:
        with pytest.raises(ApiError) as caught:
            await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(failed_id)
    assert caught.value.code == "proposal_already_active"
    assert live.proposal_id in caught.value.message
    assert world.log == []


@pytest.mark.parametrize("failed_command", ["ab-tests create", "ab-tests start"])
async def test_retry_after_test_creation_was_attempted_does_not_duplicate_a_test(factory, failed_command):
    world = World(fail=failed_command)
    out, pid = await run_approve(factory, world)
    assert out.status == "failed"
    world.fail = None
    world.log.clear()
    async with factory() as s:
        with pytest.raises(ApiError) as caught:
            await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(pid)
    assert (caught.value.status, caught.value.code) == (409, "activation_retry_unsafe")
    assert world.log == []


@pytest.mark.parametrize("initial_status", ["draft", "failed", "awaiting_publish", "failed_again"])
async def test_a_concurrent_approval_cannot_create_a_second_test(factory, initial_status):
    world = World()
    async with factory() as s:
        (created,) = await ProposalService(s).create(APP, [proposal_input()])
        row = await ProposalService(s)._get(created.proposal_id)
        row.status = "failed" if initial_status == "failed_again" else initial_status
        if initial_status == "awaiting_publish":
            row.adapty = {"segment_id": "seg1"}
        await s.commit()
    async with factory() as s:
        activation = ActivationService(s, AdaptyCommands(world, ADAPTY), world)
        # Simulate another request claiming the proposal after this request read it.
        stale = await activation._proposals._get(created.proposal_id)
        async with factory() as other:
            fresh = await ProposalService(other)._get(created.proposal_id)
            if initial_status == "failed_again":
                from datetime import timedelta

                fresh.updated_at = fresh.updated_at + timedelta(seconds=1)
            else:
                fresh.status = "executing"
            await other.commit()

        async def stale_get(_):
            return stale

        activation._proposals._get = stale_get
        with pytest.raises(ApiError) as caught:
            await activation.approve(created.proposal_id)
        assert caught.value.code == "approval_in_progress"
    assert "ab-tests create" not in world.log


@pytest.mark.parametrize(
    ("arms", "offer", "expected"),
    [
        (
            [{"flow_id": "f-control", "title": "Control", "weight": 20}, {"flow_id": "f-other", "weight": 80}],
            "f-new",
            "f-control",
        ),
        (
            [
                {"flow_id": "f-control", "weight": 50},
                {"flow_id": "f-offer", "weight": 50},
                {"flow_id": "f-disabled", "weight": 0},
            ],
            "f-offer",
            "f-control",
        ),
        ([{"flow_id": "f-a", "weight": 50}, {"flow_id": "f-b", "weight": 50}], "f-new", None),
        (
            [
                {"flow_id": "f-a", "title": "control", "weight": 50},
                {"flow_id": "f-b", "title": "control", "weight": 50},
            ],
            "f-new",
            None,
        ),
        ([], "f-new", None),
    ],
)
async def test_default_test_control_selection_handles_all_arm_shapes(factory, monkeypatch, arms, offer, expected):
    monkeypatch.setitem(
        PLACEMENT, "audiences", [{"content_type": "flow_ab_test", "segment_ids": [], "ab_test_id": "existing"}]
    )
    world = World()
    world.ab_test = {"flows": arms}
    out, _ = await run_approve(factory, world, proposal_input(action={"flow_id": offer}))
    (decision,) = await decisions(factory)
    if expected:
        assert out.status == "live"
        assert decision.steps[2]["detail"]["control_flow_id"] == expected
    else:
        assert out.status == "failed"
        assert decision.steps[-1]["detail"]["code"] == "placement_control_ambiguous"
        assert "ab-tests create" not in world.log


async def test_only_a_draft_can_be_approved(factory):
    world = World()
    _, pid = await run_approve(factory, world)  # now live
    async with factory() as s:
        with pytest.raises(ApiError) as caught:
            await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(pid)
    assert (caught.value.status, caught.value.code) == (409, "invalid_transition")


async def test_autopilot_is_recorded_as_the_actor_and_the_action(factory):
    world = World()
    out, _ = await run_approve(factory, world, decided_by="autopilot", mode="autopilot")
    assert (out.decided_by, out.mode_at_decision) == ("autopilot", "autopilot")
    (decision,) = await decisions(factory)
    assert (decision.decided_by, decision.action) == ("autopilot", "autopilot_start")


async def test_publishing_is_never_called(factory):
    world = World(flow_status="draft")
    item = proposal_input(action={"flow_id": "f-new", "needs_publish": True})
    _, pid = await run_approve(factory, world, item)
    world.flow_status = "published"
    async with factory() as s:
        await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(pid)
    assert not any(c[:2] == ("flows", "publish") for c in world.cli_calls)


def test_approve_route_runs_the_activation_with_the_providers_on_app_state(api, factory):
    import asyncio

    async def create():
        async with factory() as s:
            (c,) = await ProposalService(s).create(APP, [proposal_input()])
            return c.proposal_id

    pid = asyncio.run(create())
    world = World()
    api.app.state.adapty_commands = AdaptyCommands(world, ADAPTY)
    api.app.state.membership_sync = world
    r = api.post(f"/v1/proposals/{pid}:approve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "live"
    assert r.json()["adapty"]["ab_test_id"] == "t1"
    assert api.post("/v1/proposals/pr_missing:approve").status_code == 404

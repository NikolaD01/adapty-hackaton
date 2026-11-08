"""C4: approve runs the whole Adapty sequence. Fake CLI and fake membership sync, real SQLite, no network."""

import pytest

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import SyncResult
from feature_signal.integrations.adapty.cli import AdaptyCommands
from feature_signal.repositories.decisions import DecisionRepository
from feature_signal.schemas.proposals import AppSettings, ProposalIn
from feature_signal.services.activation_service import ActivationService
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
        if command == "flows get":
            return {"id": args[2], "status": self.flow_status}
        return {}

    async def sync_users(self, app_id, ids):
        self.log.append("sync")
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


async def test_a_placement_whose_default_is_not_a_plain_flow_fails(factory, monkeypatch):
    monkeypatch.setitem(
        PLACEMENT, "audiences", [{"content_type": "flow_ab_test", "segment_ids": [], "ab_test_id": "x"}]
    )
    world = World()
    out, _ = await run_approve(factory, world)
    assert out.status == "failed"
    (decision,) = await decisions(factory)
    assert decision.steps[-1]["detail"]["code"] == "placement_default_not_a_flow"


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

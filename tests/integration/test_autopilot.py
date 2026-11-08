"""C7: autopilot approves drafts by itself, inside the limits, and never publishes. Fakes only, real SQLite."""

import json

import pytest

from feature_signal.domain.models import Condition, ProposalDraft
from feature_signal.integrations.adapty.cli import AdaptyCommands
from feature_signal.repositories.decisions import DecisionRepository
from feature_signal.schemas.proposals import AppSettings, AutopilotLimits
from feature_signal.services.activation_service import ActivationService
from feature_signal.services.autopilot_service import AutopilotService, AutopilotSink, LaunchingSink
from feature_signal.services.proposal_service import ProposalService
from tests.integration.adapty_helpers import make_factory
from tests.integration.test_activation import ADAPTY, APP, World, arg, proposal_input


@pytest.fixture
def factory(db_url):
    return make_factory(db_url)


async def setup(factory, *, mode="autopilot", max_live=3, min_holdout=10, items=()):
    async with factory() as s:
        service = ProposalService(s)
        await service.put_settings(
            APP,
            AppSettings(mode=mode, autopilot=AutopilotLimits(max_live_proposals=max_live, min_holdout_pct=min_holdout)),
        )
        created = await service.create(APP, list(items))
    return [c.proposal_id for c in created]


async def run_autopilot(factory, world):
    async with factory() as s:
        activation = ActivationService(s, AdaptyCommands(world, ADAPTY), world)
        return await AutopilotService(s, activation).run(APP)


async def statuses(factory):
    async with factory() as s:
        return {p.proposal_id: p.status for p in await ProposalService(s).list(APP)}


def drafts(n, **over):
    return [
        proposal_input(
            segment_key=f"seg{i}",
            expected_effect={"diff": float(i), "ci_low": 0.1, "ci_high": 20.0},
            action={"flow_id": f"f-offer-{i}", "needs_publish": False},
            **over,
        )
        for i in range(n)
    ]


async def test_human_mode_does_nothing(factory):
    ids = await setup(factory, mode="human", items=drafts(2))
    world = World()
    assert await run_autopilot(factory, world) == []
    assert world.cli_calls == []
    assert set((await statuses(factory)).values()) == {"draft"}
    assert len(ids) == 2


async def test_autopilot_approves_drafts_and_records_it_as_the_actor(factory):
    await setup(factory, items=drafts(1))
    world = World()
    (out,) = await run_autopilot(factory, world)
    assert (out.status, out.decided_by, out.mode_at_decision) == ("live", "autopilot", "autopilot")
    async with factory() as s:
        (decision,) = await DecisionRepository(s).list(APP)
    assert (decision.decided_by, decision.action) == ("autopilot", "autopilot_start")


async def test_it_never_starts_more_than_max_live_proposals(factory):
    await setup(factory, max_live=2, items=drafts(3))
    world = World()
    results = await run_autopilot(factory, world)
    assert len(results) == 2
    assert sorted((await statuses(factory)).values()) == ["draft", "live", "live"]


async def test_proposals_already_live_use_up_the_limit(factory):
    ids = await setup(factory, max_live=2, items=drafts(3))
    world = World()
    async with factory() as s:
        await ActivationService(s, AdaptyCommands(world, ADAPTY), world).approve(ids[0])  # a human launched one
    results = await run_autopilot(factory, World())
    assert len(results) == 1
    assert sorted((await statuses(factory)).values()) == ["draft", "live", "live"]


async def test_the_most_valuable_drafts_go_first(factory):
    ids = await setup(factory, max_live=1, items=drafts(3))  # expected diff 0, 1, 2
    await run_autopilot(factory, World())
    live = [pid for pid, st in (await statuses(factory)).items() if st == "live"]
    assert live == [ids[2]]


async def test_a_too_small_holdout_is_raised_to_the_minimum_and_the_edit_is_recorded(factory):
    await setup(factory, min_holdout=15, items=[drafts(1)[0].model_copy(update={"holdout_pct": 5})])
    world = World()
    (out,) = await run_autopilot(factory, world)
    create = next(c for c in world.cli_calls if c[:2] == ("ab-tests", "create"))
    assert [a["weight"] for a in json.loads(arg(create, "--flows"))] == [15, 85]
    assert out.holdout_pct == 15
    assert [(e.field, e.from_, e.to) for e in out.edits] == [("holdout_pct", 5, 15)]


async def test_a_larger_holdout_is_left_alone(factory):
    await setup(factory, min_holdout=10, items=[drafts(1)[0].model_copy(update={"holdout_pct": 30})])
    (out,) = await run_autopilot(factory, World())
    assert out.holdout_pct == 30
    assert out.edits == []


async def test_a_new_draft_flow_waits_for_a_human_publish_and_takes_a_slot(factory):
    items = [proposal_input(segment_key="new", action={"flow_id": "f-new", "needs_publish": True})] + drafts(2)
    await setup(factory, max_live=2, items=items)
    world = World(flow_status="draft")
    results = await run_autopilot(factory, world)
    assert sorted(r.status for r in results) == ["awaiting_publish", "live"]
    assert not any(c[:2] == ("flows", "publish") for c in world.cli_calls)


async def test_a_failed_launch_does_not_use_up_a_slot(factory):
    await setup(factory, max_live=1, items=drafts(3))
    world = World(fail="segments create")
    results = await run_autopilot(factory, world)
    assert [r.status for r in results] == ["failed", "failed", "failed"]


async def test_the_sink_stores_b_drafts_and_launches_them_in_autopilot(factory):
    draft = ProposalDraft(
        segment_key="power_editor",
        trigger_placement="main",
        condition=Condition(field="p_segment", op="IN", value=["power_editor"]),
        flow_id="f-lifetime",
        flow_name="Lifetime",
        expected_diff=14.4,
        ci_low=9.1,
        ci_high=19.8,
        reason="r",
    )
    await setup(factory)
    world = World()
    async with factory() as s:
        activation = ActivationService(s, AdaptyCommands(world, ADAPTY), world)
        ids = await AutopilotSink(s, AutopilotService(s, activation)).create_many(APP, [draft])
    assert (await statuses(factory)) == {ids[0]: "live"}


async def test_the_sink_leaves_drafts_alone_in_human_mode(factory):
    draft = ProposalDraft(
        segment_key="p",
        trigger_placement="main",
        condition=Condition(field="p_segment", op="IN", value=["p"]),
        flow_id="f-lifetime",
        flow_name="Lifetime",
        expected_diff=1.0,
        ci_low=0.5,
        ci_high=1.5,
        reason="r",
    )
    await setup(factory, mode="human")
    world = World()
    async with factory() as s:
        activation = ActivationService(s, AdaptyCommands(world, ADAPTY), world)
        ids = await AutopilotSink(s, AutopilotService(s, activation)).create_many(APP, [draft])
    assert (await statuses(factory)) == {ids[0]: "draft"}
    assert world.cli_calls == []


def test_posting_proposals_in_autopilot_launches_them(api, factory):
    import asyncio

    asyncio.run(setup(factory, items=[]))
    world = World()
    api.app.state.adapty_commands = AdaptyCommands(world, ADAPTY)
    api.app.state.membership_sync = world
    body = {"proposals": [json.loads(drafts(1)[0].model_dump_json())]}
    r = api.post(f"/v1/apps/{APP}/proposals", json=body)
    assert r.status_code == 200, r.text
    assert [p["status"] for p in r.json()] == ["live"]
    assert r.json()[0]["decided_by"] == "autopilot"


async def test_autopilot_leaves_drafts_for_other_placements_to_a_human(factory):
    ids = await setup(
        factory,
        items=[
            proposal_input(segment_key="main_seg", trigger_placement="main"),
            proposal_input(
                segment_key="onb_seg",
                trigger_placement="onboarding",
                expected_effect={"diff": 99.0, "ci_low": 1.0, "ci_high": 120.0},  # more valuable, still skipped
            ),
        ],
    )
    world = World()
    async with factory() as s:
        activation = ActivationService(s, AdaptyCommands(world, ADAPTY), world)
        results = await AutopilotService(s, activation, allowed_placements={"main"}).run(APP)
    assert [r.trigger_placement for r in results] == ["main"]
    assert await statuses(factory) == {ids[0]: "live", ids[1]: "draft"}


async def test_launching_sink_moves_main_drafts_and_schedules_one_pass(factory):
    await setup(factory, mode="human")
    scheduled, launched = [], []

    async def launch(app_id):
        launched.append(app_id)

    def draft(placement, key):
        return ProposalDraft(
            segment_key=key,
            trigger_placement=placement,
            condition=Condition(field="p_segment", op="IN", value=[key]),
            flow_id="f-lifetime",
            flow_name="Lifetime",
            expected_diff=1.0,
            ci_low=0.5,
            ci_high=1.5,
            reason="r",
        )

    async with factory() as s:
        sink = LaunchingSink(s, launch, placement_map={"main": "fs_test"}, schedule=scheduled.append)
        ids = await sink.create_many(APP, [draft("main", "a"), draft("onboarding", "b")])
    async with factory() as s:
        stored = {p.proposal_id: p.trigger_placement for p in await ProposalService(s).list(APP)}
    assert stored == {ids[0]: "fs_test", ids[1]: "onboarding"}
    assert len(scheduled) == 1 and launched == []  # the pass runs after the insight run returns
    await scheduled[0]
    assert launched == [APP]


LIMITS = {"max_live_proposals": 3, "min_holdout_pct": 10, "allow_publish_flow": False}
AUTOPILOT = {"mode": "autopilot", "autopilot": LIMITS}


def wire_fakes(api, factory, world):
    api.app.state.adapty_commands = AdaptyCommands(world, ADAPTY)
    api.app.state.membership_sync = world
    api.app.state.session_factory = factory


def test_switching_to_autopilot_launches_the_waiting_drafts_after_the_answer(api, factory):
    import asyncio

    ids = asyncio.run(setup(factory, mode="human", items=drafts(1)))
    world = World()
    wire_fakes(api, factory, world)
    r = api.put(f"/v1/apps/{APP}/settings", json=AUTOPILOT)
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "autopilot"
    assert asyncio.run(statuses(factory)) == {ids[0]: "live"}


def test_switching_to_autopilot_respects_the_placement_limit(api, factory):
    import asyncio

    ids = asyncio.run(setup(factory, mode="human", items=drafts(1)))
    world = World()
    wire_fakes(api, factory, world)
    api.app.state.autopilot_placements = {APP: frozenset({"fs_test"})}  # the draft is for `main`
    assert api.put(f"/v1/apps/{APP}/settings", json=AUTOPILOT).status_code == 200
    assert asyncio.run(statuses(factory)) == {ids[0]: "draft"}
    assert world.cli_calls == []


def test_switching_to_human_launches_nothing(api, factory):
    import asyncio

    ids = asyncio.run(setup(factory, mode="human", items=drafts(1)))
    world = World()
    wire_fakes(api, factory, world)
    assert api.put(f"/v1/apps/{APP}/settings", json={**AUTOPILOT, "mode": "human"}).status_code == 200
    assert asyncio.run(statuses(factory)) == {ids[0]: "draft"}
    assert world.cli_calls == []


async def test_a_repeated_insight_run_does_not_queue_the_same_offer_twice(factory):
    await setup(factory, mode="human")
    draft = ProposalDraft(
        segment_key="a",
        trigger_placement="main",
        condition=Condition(field="p_segment", op="IN", value=["a"]),
        flow_id="f-lifetime",
        flow_name="Lifetime",
        expected_diff=1.0,
        ci_low=0.5,
        ci_high=1.5,
        reason="r",
    )

    async def launch(app_id):
        return None

    async with factory() as s:
        first = await LaunchingSink(
            s, launch, placement_map={"main": "fs_test"}, schedule=lambda c: c.close()
        ).create_many(APP, [draft])
    async with factory() as s:
        second = await LaunchingSink(
            s, launch, placement_map={"main": "fs_test"}, schedule=lambda c: c.close()
        ).create_many(APP, [draft])
    assert first == second
    assert len(await statuses(factory)) == 1

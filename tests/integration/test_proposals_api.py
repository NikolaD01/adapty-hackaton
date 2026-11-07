"""C3: proposals store, edit whitelist, reject, settings - real SQLite, no network."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from feature_signal.db.session import make_engine
from feature_signal.domain.models import Condition, ProposalDraft
from feature_signal.services.proposal_service import ProposalService

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
BASE = f"/v1/apps/{APP}"

PROPOSAL = {
    "trigger_placement": "main",
    "segment_key": "power_editor",
    "condition": {"attribute": "p_segment", "op": "IN", "value": ["power_editor"]},
    "adapty_filters": [{"field": "subscription_state", "op": "IN", "value": ["never_subscribed"]}],
    "action": {"type": "flow", "flow_id": "f-lifetime", "flow_name": "Main - Lifetime anchor", "needs_publish": False},
    "holdout_pct": 20,
    "cooldown_days": 7,
    "expected_effect": {"metric": "net_revenue_90d", "diff": 14.4, "ci_low": 9.1, "ci_high": 19.8},
    "reason": "Users with 5+ edits gain $14.40 net from the lifetime anchor",
    "evidence": {"run_id": "ir_1"},
    "created_by": "ai",
}


def create(api, **overrides):
    r = api.post(f"{BASE}/proposals", json={"proposals": [{**PROPOSAL, **overrides}]})
    assert r.status_code == 200, r.text
    return r.json()[0]


def test_create_returns_a_draft_with_an_id_and_empty_edits(api):
    p = create(api)
    assert p["status"] == "draft"
    assert p["proposal_id"].startswith("pr_")
    assert p["app_id"] == APP
    assert p["created_by"] == "ai"
    assert p["decided_by"] is None
    assert p["edits"] == []
    assert p["adapty"] == {"segment_id": None, "placement_id": None, "ab_test_id": None, "attributes_written": 0}
    assert p["condition"]["value"] == ["power_editor"]


def test_list_and_filter_by_status(api):
    a = create(api)
    b = create(api, segment_key="other")
    api.post(f"/v1/proposals/{b['proposal_id']}:reject", json={"reason": "no"})
    assert {p["proposal_id"] for p in api.get(f"{BASE}/proposals").json()} == {a["proposal_id"], b["proposal_id"]}
    drafts = api.get(f"{BASE}/proposals", params={"status": "draft"}).json()
    assert [p["proposal_id"] for p in drafts] == [a["proposal_id"]]


def test_list_is_scoped_to_the_app(api):
    create(api)
    assert api.get("/v1/apps/another-app/proposals").json() == []


def test_patch_changes_only_whitelisted_fields_and_records_each_edit(api):
    p = create(api)
    r = api.patch(
        f"/v1/proposals/{p['proposal_id']}",
        json={
            "holdout_pct": 30,
            "flow_id": "f-other",
            "condition_value": ["x"],
            "trigger_placement": "ai_limit_reached",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["holdout_pct"] == 30
    assert body["action"]["flow_id"] == "f-other"
    assert body["condition"]["value"] == ["x"]
    assert body["trigger_placement"] == "ai_limit_reached"
    by_field = {e["field"]: e for e in body["edits"]}
    assert set(by_field) == {"holdout_pct", "flow_id", "condition_value", "trigger_placement"}
    assert (by_field["holdout_pct"]["from"], by_field["holdout_pct"]["to"]) == (20, 30)
    assert by_field["flow_id"]["from"] == "f-lifetime"
    assert all(e["at"] for e in body["edits"])


def test_patch_with_the_same_value_adds_no_edit(api):
    p = create(api)
    body = api.patch(f"/v1/proposals/{p['proposal_id']}", json={"holdout_pct": 20}).json()
    assert body["edits"] == []


def test_patch_unknown_field_is_422_and_nothing_changes(api):
    p = create(api)
    r = api.patch(f"/v1/proposals/{p['proposal_id']}", json={"holdout_pct": 30, "paywall_json": {"x": 1}})
    assert r.status_code == 422
    assert api.get(f"{BASE}/proposals").json()[0]["holdout_pct"] == 20


def test_patch_is_only_allowed_in_draft(api):
    p = create(api)
    api.post(f"/v1/proposals/{p['proposal_id']}:reject", json={"reason": "no"})
    r = api.patch(f"/v1/proposals/{p['proposal_id']}", json={"holdout_pct": 30})
    assert (r.status_code, r.json()["error"]["code"]) == (409, "proposal_not_editable")


def test_patch_unknown_proposal_is_404(api):
    r = api.patch("/v1/proposals/pr_missing", json={"holdout_pct": 30})
    assert (r.status_code, r.json()["error"]["code"]) == (404, "proposal_not_found")


def test_reject_sets_status_actor_and_writes_a_decision_with_the_reason(api):
    p = create(api)
    r = api.post(f"/v1/proposals/{p['proposal_id']}:reject", json={"reason": "Too small a segment"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["status"], body["decided_by"], body["mode_at_decision"]) == ("rejected", "human", "human")


def test_reject_requires_a_reason(api):
    p = create(api)
    assert api.post(f"/v1/proposals/{p['proposal_id']}:reject", json={}).status_code == 422
    assert api.post(f"/v1/proposals/{p['proposal_id']}:reject", json={"reason": ""}).status_code == 422


def test_reject_twice_is_409(api):
    p = create(api)
    api.post(f"/v1/proposals/{p['proposal_id']}:reject", json={"reason": "no"})
    r = api.post(f"/v1/proposals/{p['proposal_id']}:reject", json={"reason": "again"})
    assert (r.status_code, r.json()["error"]["code"]) == (409, "invalid_transition")


def test_settings_default_to_human_with_the_contract_limits(api):
    assert api.get(f"{BASE}/settings").json() == {
        "mode": "human",
        "autopilot": {"max_live_proposals": 3, "min_holdout_pct": 10, "allow_publish_flow": False},
    }


def test_put_settings_round_trips(api):
    new = {
        "mode": "autopilot",
        "autopilot": {"max_live_proposals": 2, "min_holdout_pct": 15, "allow_publish_flow": False},
    }
    assert api.put(f"{BASE}/settings", json=new).json() == new
    assert api.get(f"{BASE}/settings").json() == new


@pytest.mark.parametrize(
    "bad",
    [
        {"mode": "robot"},
        {"mode": "autopilot", "autopilot": {"allow_publish_flow": True}},
        {"mode": "autopilot", "autopilot": {"min_holdout_pct": 90}},
    ],
    ids=["unknown-mode", "publish-allowed", "holdout-too-high"],
)
def test_put_settings_rejects_invalid_values(api, bad):
    assert api.put(f"{BASE}/settings", json=bad).status_code == 422
    assert api.get(f"{BASE}/settings").json()["mode"] == "human"


def test_settings_are_per_app(api):
    api.put(f"{BASE}/settings", json={"mode": "autopilot"})
    assert api.get("/v1/apps/another-app/settings").json()["mode"] == "human"


async def test_create_many_implements_the_proposal_sink_for_b(db_url):
    engine = make_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"))
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    draft = ProposalDraft(
        segment_key="power_editor",
        trigger_placement="main",
        condition=Condition(field="p_segment", op="IN", value=["power_editor"]),
        flow_id="f-lifetime",
        flow_name="Main - Lifetime anchor",
        expected_diff=14.4,
        ci_low=9.1,
        ci_high=19.8,
        reason="lift",
        adapty_filters=[Condition(field="subscription_state", op="IN", value=["never_subscribed"])],
        highlight_feature="ai_generate",
    )
    async with factory() as session:
        ids = await ProposalService(session).create_many(APP, [draft, draft])
        assert len(ids) == 2
        assert len(set(ids)) == 2
        stored = await ProposalService(session).list(APP, "draft")
    assert {p.proposal_id for p in stored} == set(ids)
    first = stored[0]
    assert first.created_by == "ai"
    assert first.condition.attribute == "p_segment"
    assert first.action.highlight_feature == "ai_generate"
    assert first.adapty_filters[0].field == "subscription_state"
    assert first.expected_effect.diff == 14.4
    await engine.dispose()

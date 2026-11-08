"""C5: the decision log API - newest first, contract shape, scoped to the app."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from feature_signal.db.session import make_engine
from feature_signal.repositories.decisions import DecisionRepository
from feature_signal.schemas.proposals import ProposalIn
from feature_signal.services.proposal_service import ProposalService

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
PROPOSAL = ProposalIn.model_validate(
    {
        "trigger_placement": "main",
        "segment_key": "power_editor",
        "condition": {"attribute": "p_segment", "op": "IN", "value": ["power_editor"]},
        "action": {"flow_id": "f1"},
        "expected_effect": {"diff": 1.0, "ci_low": 0.5, "ci_high": 1.5},
        "reason": "r",
    }
)


def seed_two_decisions(db_url, app_id=APP):
    async def go():
        engine = make_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"))
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as s:
            (p,) = await ProposalService(s).create(app_id, [PROPOSAL])
            repo = DecisionRepository(s)
            await repo.add(
                app_id,
                p.proposal_id,
                "human",
                "approve",
                [{"step": "write_attributes", "ok": True, "detail": {"profiles": 3}}],
            )
            await asyncio.sleep(0.01)
            await repo.add(
                app_id,
                p.proposal_id,
                "autopilot",
                "autopilot_start",
                [{"step": "segments_create", "ok": False, "detail": {"code": "x"}}],
            )
            await s.commit()
            await engine.dispose()
            return p.proposal_id

    return asyncio.run(go())


def test_empty_log_is_an_empty_list(api):
    assert api.get(f"/v1/apps/{APP}/decisions").json() == []


def test_decisions_are_listed_newest_first_in_the_contract_shape(api, db_url):
    pid = seed_two_decisions(db_url)
    body = api.get(f"/v1/apps/{APP}/decisions").json()
    assert [d["action"] for d in body] == ["autopilot_start", "approve"]
    first = body[0]
    assert set(first) == {"decision_id", "proposal_id", "decided_by", "action", "steps", "at"}
    assert first["decision_id"].startswith("dc_")
    assert (first["proposal_id"], first["decided_by"]) == (pid, "autopilot")
    assert first["steps"] == [{"step": "segments_create", "ok": False, "detail": {"code": "x"}}]
    assert body[1]["steps"][0]["detail"] == {"profiles": 3}


def test_the_log_is_scoped_to_the_app(api, db_url):
    seed_two_decisions(db_url)
    assert api.get("/v1/apps/another-app/decisions").json() == []


def test_proposal_filter_returns_only_that_proposals_decisions(api, db_url):
    pid = seed_two_decisions(db_url)
    assert len(api.get(f"/v1/apps/{APP}/decisions", params={"proposal_id": pid}).json()) == 2
    assert api.get(f"/v1/apps/{APP}/decisions", params={"proposal_id": "pr_other"}).json() == []

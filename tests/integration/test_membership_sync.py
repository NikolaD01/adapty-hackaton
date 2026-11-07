"""C9 on a real SQLite database: stores, proposals and the written-state table work together."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from feature_signal.db.session import make_engine
from feature_signal.db.tables import ProposalRow
from feature_signal.domain.models import FeatureTier
from feature_signal.repositories.tiers import TierRepository
from feature_signal.repositories.values import ValueRepository
from feature_signal.schemas.proposals import ProposalIn
from feature_signal.services.membership_service import SqlMembershipSync
from feature_signal.services.proposal_service import ProposalService
from tests.fakes import FakeAttributeWriter

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
BASE = f"/v1/apps/{APP}"

PROPOSAL = ProposalIn.model_validate(
    {
        "trigger_placement": "main",
        "segment_key": "power_editor",
        "condition": {"attribute": "p_segment", "op": "IN", "value": ["power_editor"]},
        "action": {"flow_id": "f1"},
        "expected_effect": {"diff": 1.0, "ci_low": 0.5, "ci_high": 1.5},
        "reason": "r",
        "evidence": {"segment_conditions": [{"field": "edits_1d", "op": ">=", "value": 5}]},
    }
)


@pytest.fixture
def factory(db_url):
    engine = make_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"))
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def seed(factory):
    async with factory() as s:
        await ValueRepository(s).put_many(APP, "ai_uses_7d", {"u1": 9.0, "u2": 1.0})
        await ValueRepository(s).put_many(APP, "edits_1d", {"u1": 6.0, "u2": 0.0})
        await TierRepository(s).put_many(APP, [FeatureTier("ai_generate", "ai_uses_7d", 2, 7, passed=True)])
        await s.commit()
        (created,) = await ProposalService(s).create(APP, [PROPOSAL])
        row = await s.get(ProposalRow, created.proposal_id)
        row.status = "live"  # activation (C4) sets this; here we only need a live proposal
        await s.commit()


async def test_sync_writes_then_stays_quiet_and_persists_what_it_wrote(factory):
    await seed(factory)
    writer = FakeAttributeWriter()
    sync = SqlMembershipSync(factory, writer)

    first = await sync.sync_users(APP, None)
    assert dict(writer.writes) == {
        "u1": {"f_ai_generate_tier": "high", "p_segment": "power_editor"},
        "u2": {"f_ai_generate_tier": "low"},
    }
    assert (first.checked, first.changed, first.attributes_written) == (2, 2, 3)

    writer.writes.clear()
    second = await sync.sync_users(APP, None)  # a new session: the state must come from the table
    assert writer.writes == []
    assert (second.changed, second.attributes_written) == (0, 0)

    async with factory() as s:
        await ValueRepository(s).put_many(APP, "edits_1d", {"u1": 1.0})
        await s.commit()
    await sync.sync_users(APP, ["u1"])
    assert writer.writes == [("u1", {"p_segment": None})]


def test_membership_route_returns_counts_and_uses_the_writer(api, factory):
    import asyncio

    asyncio.run(seed(factory))
    writer = FakeAttributeWriter()
    api.app.state.attribute_writer = writer
    r = api.post(f"{BASE}/membership:sync", json={"customer_user_ids": ["u1"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"checked": 1, "changed": 1, "attributes_written": 2}
    assert writer.writes == [("u1", {"f_ai_generate_tier": "high", "p_segment": "power_editor"})]
    again = api.post(f"{BASE}/membership:sync", json={"customer_user_ids": ["u1"]})
    assert again.json() == {"checked": 1, "changed": 0, "attributes_written": 0}


def test_membership_route_with_null_ids_means_everyone(api):
    api.app.state.attribute_writer = FakeAttributeWriter()
    r = api.post(f"{BASE}/membership:sync", json={})
    assert r.status_code == 200
    assert r.json()["checked"] == 0

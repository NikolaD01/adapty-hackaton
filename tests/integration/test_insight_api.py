import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from feature_signal.api.v1.insights import BrainRuntime, configure_brain
from feature_signal.db.session import make_engine
from feature_signal.repositories.tiers import TierRepository
from feature_signal.services.insight_service import PublishedFlow
from tests.fakes import FakeProposalSink
from tests.service.test_insight_service import Dataset


def setup_runtime(api):
    sink = FakeProposalSink()
    configure_brain(
        api.app,
        "app",
        BrainRuntime(
            as_of="2026-05-01T00:00:00Z",
            dataset=Dataset(),
            proposal_sink_factory=lambda session: sink,
            published_flows={"main_lifetime": PublishedFlow("published-flow", "Lifetime", True)},
            offline_columns=("edits",),
            offline_features={"edits": "editor"},
            explain=False,
        ),
    )
    return sink


def test_run_latest_and_real_tier_repository(api, db_url):
    sink = setup_runtime(api)
    assert api.get("/v1/apps/app/insights/latest").status_code == 404
    response = api.post("/v1/apps/app/insights:run", json={"source": "offline"})
    assert response.status_code == 200
    body = response.json()
    assert {"rankings", "segments", "uplift", "tiers", "hypotheses"} <= body.keys()
    assert body["tiers"] and body["segments"] and sink.created
    assert api.get("/v1/apps/app/insights/latest").json()["run_id"] == body["run_id"]

    async def read_persisted_tiers():
        engine = make_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"))
        async with async_sessionmaker(engine)() as session:
            tiers = await TierRepository(session).list("app")
        await engine.dispose()
        return tiers

    tiers = asyncio.run(read_persisted_tiers())
    assert body["tiers"][0]["feature"] == "editor" and body["tiers"][0]["passed"]
    assert tiers == []  # offline tiers are reported, never stored: only a live run writes the TierStore


def test_invalid_source_and_missing_composition_have_clear_errors(api):
    setup_runtime(api)
    response = api.post("/v1/apps/app/insights:run", json={"source": "invalid"})
    assert response.status_code == 422
    response = api.post("/v1/apps/unconfigured/insights:run", json={"source": "offline"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "brain_not_configured"


def test_live_request_with_no_values_reports_actual_offline_fallback(api):
    setup_runtime(api)
    response = api.post("/v1/apps/app/insights:run", json={"source": "live"})
    assert response.status_code == 200
    assert response.json()["source"] == "offline"


def test_live_run_uses_real_value_store_with_verified_identity_and_measurement(api, db_url):
    from feature_signal.repositories.values import ValueRepository

    setup_runtime(api)
    assert (
        api.post(
            "/v1/apps/app/features",
            json={
                "key": "editor",
                "name": "Editor",
                "description": "Photo editing",
            },
        ).status_code
        == 200
    )
    assert (
        api.post(
            "/v1/apps/app/event-types",
            json={
                "key": "edit",
                "name": "Edit",
                "description": "Photo edited",
                "features": ["editor"],
            },
        ).status_code
        == 200
    )
    assert (
        api.post(
            "/v1/apps/app/rules",
            json={
                "key": "edits",
                "name": "Edits",
                "description": "Verified baseline edit count",
                "feature": "editor",
                "definition": {"event_keys": ["edit"], "measure": "count"},
            },
        ).status_code
        == 200
    )
    values = {f"u{i:05d}": float(i // 1000) for i in range(3000)}
    runtime = api.app.state.brain_runtimes["app"]
    runtime.user_id_map = {user: user for user in values}
    runtime.live_outcome_rules = frozenset({"edits"})

    async def write_values():
        engine = make_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"))
        async with async_sessionmaker(engine)() as session:
            await ValueRepository(session).put_many("app", "edits", values)
            await session.commit()
        await engine.dispose()

    asyncio.run(write_values())
    response = api.post("/v1/apps/app/insights:run", json={"source": "live"})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "live"
    assert any(item["feature"] == "edits" and item["passed"] for item in body["rankings"])
    assert any(item["rule_key"] == "edits" and item["passed"] for item in body["tiers"])

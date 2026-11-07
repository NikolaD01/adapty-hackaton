"""A7: recompute, ValueStore.matrix, paged values, feature profile with tiers, values fresh after ingest."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from feature_signal.db.session import make_engine
from feature_signal.domain.models import FeatureTier
from feature_signal.repositories.tiers import TierRepository
from feature_signal.repositories.values import ValueRepository

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
BASE = f"/v1/apps/{APP}"


def at(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def ev(i: int, user: str, key: str = "generate_click", days_ago: float = 0.1, **props) -> dict:
    return {
        "event_id": f"00000000-0000-4000-8000-{i:012d}",
        "customer_user_id": user,
        "key": key,
        "occurred_at": at(days_ago),
        "props": props,
    }


def setup(api) -> None:
    api.post(f"{BASE}/features", json={"key": "ai_generate", "name": "AI generation", "description": "d"})
    for key in ("generate_click", "regenerate_click"):
        api.post(f"{BASE}/event-types", json={"key": key, "name": key, "description": "d", "features": ["ai_generate"]})


def run(db_url: str, fn):
    async def go():
        engine = make_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"))
        async with async_sessionmaker(engine, class_=AsyncSession)() as s:
            out = await fn(s)
            await s.commit()
        await engine.dispose()
        return out

    return asyncio.run(go())


def test_ingest_refreshes_the_users_values_immediately(api):
    setup(api)
    api.post(f"{BASE}/events", json={"events": [ev(1, "u_42"), ev(2, "u_42", "regenerate_click")]})
    profile = api.get(f"{BASE}/users/u_42/features").json()
    item = profile["features"][0]
    assert item["feature"] == "ai_generate" and item["name"] == "AI generation"
    assert item["values"]["ai_generate_uses_7d"] == 2
    assert item["values"]["ai_generate_used_regenerate_click"] == 1
    assert item["tier"] is None  # no measured tier yet


def test_recompute_three_users_two_rules_gives_the_expected_matrix(api, db_url):
    api.post(f"{BASE}/features", json={"key": "export", "name": "Export", "description": "d"})
    api.post(f"{BASE}/event-types", json={"key": "export_click", "name": "e", "description": "d", "features": []})
    api.post(
        f"{BASE}/events",
        json={"events": [ev(1, "a", "export_click"), ev(2, "a", "export_click", 9), ev(3, "b", "export_click")]},
    )
    for key, window in (("exports_total", None), ("exports_7d", 7)):
        api.post(
            f"{BASE}/rules",
            json={
                "key": key,
                "name": key,
                "description": "d",
                "definition": {"event_keys": ["export_click"], "measure": "count", "window_days": window},
            },
        )
    api.post(f"{BASE}/events", json={"events": [ev(4, "c", "export_click", 20)]})
    assert api.post(f"{BASE}/values:recompute").json() == {"users": 3, "rules": 2}
    m = run(db_url, lambda s: ValueRepository(s).matrix(APP))
    assert m.users == ["a", "b", "c"] and m.columns == ["exports_7d", "exports_total"]
    assert m.values == [[1.0, 2.0], [1.0, 1.0], [0.0, 1.0]]


def test_values_are_paged_with_a_cursor(api):
    setup(api)
    api.post(f"{BASE}/events", json={"events": [ev(i, f"u_{i}") for i in range(3)]})
    first = api.get(f"{BASE}/values", params={"rule_key": "ai_generate_uses_7d", "limit": 2}).json()
    assert [i["customer_user_id"] for i in first["items"]] == ["u_0", "u_1"] and first["next_cursor"] == "2"
    rest = api.get(
        f"{BASE}/values", params={"rule_key": "ai_generate_uses_7d", "limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert [i["customer_user_id"] for i in rest["items"]] == ["u_2"] and rest["next_cursor"] is None
    assert api.get(f"{BASE}/values", params={"cursor": "x"}).status_code == 422


def test_profile_shows_a_tier_only_when_it_passed(api, db_url):
    setup(api)
    api.post(f"{BASE}/events", json={"events": [ev(i, "u_42") for i in range(9)]})
    tiers = [FeatureTier(feature="ai_generate", rule_key="ai_generate_uses_7d", low_max=2, mid_max=7, passed=True)]
    run(db_url, lambda s: TierRepository(s).put_many(APP, tiers))
    assert api.get(f"{BASE}/users/u_42/features").json()["features"][0]["tier"] == "high"
    run(
        db_url,
        lambda s: TierRepository(s).put_many(APP, [FeatureTier("ai_generate", "ai_generate_uses_7d", 2, 7, False)]),
    )
    assert api.get(f"{BASE}/users/u_42/features").json()["features"][0]["tier"] is None
    assert run(db_url, lambda s: TierRepository(s).list(APP))[0].passed is False


def test_unknown_user_has_empty_values(api):
    setup(api)
    body = api.get(f"{BASE}/users/nobody/features").json()
    assert body["features"][0]["values"] == {} and body["features"][0]["computed_at"] is None

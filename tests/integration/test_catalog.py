"""A2: features and event catalog over HTTP, with default rules kept in step."""

from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from feature_signal.db.tables import RuleRow

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
BASE = f"/v1/apps/{APP}"
FEATURE = {
    "key": "ai_generate",
    "name": "AI generation",
    "description": "Generate an image from a prompt",
    "plans": ["premium"],
}


def event(key: str, features=("ai_generate",), name: str | None = None) -> dict:
    return {"key": key, "name": name or key, "description": f"User sent {key}", "features": list(features)}


def rules_in_db(db_url: str) -> dict[str, RuleRow]:
    with Session(create_engine(db_url)) as s:
        return {r.key: r for r in s.scalars(select(RuleRow))}


def test_feature_round_trips(api):
    r = api.post(f"{BASE}/features", json=FEATURE)
    assert r.status_code == 200, r.text
    assert r.json()["plans"] == ["premium"]
    assert [f["key"] for f in api.get(f"{BASE}/features").json()] == ["ai_generate"]


def test_three_events_give_six_default_rules(api, db_url):
    api.post(f"{BASE}/features", json=FEATURE)
    for key in ("generate_click", "image_upload", "regenerate_click"):
        assert api.post(f"{BASE}/event-types", json=event(key)).status_code == 200
    rules = rules_in_db(db_url)
    assert len(rules) == 6
    assert rules["ai_generate_uses_7d"].definition["event_keys"] == [
        "generate_click",
        "image_upload",
        "regenerate_click",
    ]
    assert {r.source for r in rules.values()} == {"default"}
    catalog = api.get(f"{BASE}/event-types").json()
    assert [(e["key"], e["features"]) for e in catalog] == [
        ("generate_click", ["ai_generate"]),
        ("image_upload", ["ai_generate"]),
        ("regenerate_click", ["ai_generate"]),
    ]


def test_re_registering_an_event_updates_it_and_keeps_its_id(api):
    api.post(f"{BASE}/features", json=FEATURE)
    first = api.post(f"{BASE}/event-types", json=event("generate_click", name="Generate")).json()
    second = api.post(f"{BASE}/event-types", json=event("generate_click", name="Generate clicked"))
    assert second.status_code == 200
    body = second.json()
    assert body["name"] == "Generate clicked"
    assert body["action_id"] == first["action_id"]
    assert body["created_at"] == first["created_at"]
    assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")
    assert len(api.get(f"{BASE}/event-types").json()) == 1


def test_unknown_feature_is_refused(api):
    r = api.post(f"{BASE}/event-types", json=event("generate_click", features=("nope",)))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unknown_feature"
    assert r.json()["error"]["details"] == {"features": ["nope"]}


def test_moving_an_event_between_features_refreshes_both(api, db_url):
    api.post(f"{BASE}/features", json=FEATURE)
    api.post(f"{BASE}/features", json={**FEATURE, "key": "export", "name": "Export", "plans": []})
    api.post(f"{BASE}/event-types", json=event("generate_click"))
    api.post(f"{BASE}/event-types", json=event("hd_export", features=("ai_generate", "export")))
    rules = rules_in_db(db_url)
    assert rules["ai_generate_uses_total"].definition["event_keys"] == ["generate_click", "hd_export"]
    assert rules["export_uses_total"].definition["event_keys"] == ["hd_export"]
    api.post(f"{BASE}/event-types", json=event("hd_export", features=("export",)))
    assert rules_in_db(db_url)["ai_generate_uses_total"].definition["event_keys"] == ["generate_click"]


def test_default_refresh_never_overwrites_a_human_rule(api, db_url):
    api.post(f"{BASE}/features", json=FEATURE)
    with Session(create_engine(db_url)) as s:
        s.add(
            RuleRow(
                app_id=APP,
                key="ai_generate_uses_7d",
                name="mine",
                description="d",
                source="human",
                feature="ai_generate",
                definition={"event_keys": ["x"], "measure": "count"},
                created_at=datetime.now(timezone.utc),
            )
        )
        s.commit()
    api.post(f"{BASE}/event-types", json=event("generate_click"))
    assert rules_in_db(db_url)["ai_generate_uses_7d"].definition["event_keys"] == ["x"]


def test_feature_key_longer_than_22_is_refused(api):
    assert api.post(f"{BASE}/features", json={**FEATURE, "key": "a" * 23}).status_code == 422

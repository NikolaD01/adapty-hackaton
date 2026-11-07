"""A8: the demo loader produces synthetic, deterministic, behavior-consistent events through the real API."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "load_demo_events", Path(__file__).parents[2] / "scripts" / "load_demo_events.py"
)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
APP = loader.APP_ID


def seed_user(i: int, edits: float, paying: bool = False, imports: float = 5) -> dict:
    tx = [{"product": "annual", "usd": 49.99, "refunded": None}] if paying else []
    return {"i": i, "attrs": {"ai_edits_first_day": edits, "photos_imported": imports}, "tx": tx}


def test_events_are_synthetic_deterministic_and_use_seed_ids():
    a = loader.user_events(seed_user(7, 5), "282506", NOW)
    b = loader.user_events(seed_user(7, 5), "282506", NOW)
    assert a == b
    assert {e["customer_user_id"] for e in a} == {"lumen_282506_00007"}
    assert all(e["props"]["synthetic"] is True for e in a)
    assert len({e["event_id"] for e in a}) == len(a)


def test_heavy_editors_produce_more_edits_than_light_ones():
    def edits(u):
        return sum(e["key"] in ("bg_remove", "ai_enhance") for e in loader.user_events(u, "282506", NOW))

    heavy = sum(edits(seed_user(i, 9)) for i in range(30))
    light = sum(edits(seed_user(i, 1)) for i in range(30))
    assert heavy > 4 * light


def test_only_free_users_get_blocked_hd_exports_and_edits_left():
    free = [e for i in range(40) for e in loader.user_events(seed_user(i, 8), "282506", NOW)]
    paid = [e for i in range(40) for e in loader.user_events(seed_user(i, 8, paying=True), "282506", NOW)]
    assert any(e["key"] == "pt_track_hd_export_blocked" for e in free)
    assert not any(e["key"] == "pt_track_hd_export_blocked" for e in paid)
    assert all("edits_left" in e["props"] for e in free if e["key"] == "ai_enhance")
    assert not any("edits_left" in e["props"] for e in paid if e["key"] == "ai_enhance")


def test_load_through_the_api_twice_is_idempotent(api):
    def post(path, body):
        r = api.post(path, json=body)
        assert r.status_code == 200, r.text
        return r.json()

    users = [seed_user(i, edits=i % 10) for i in range(12)]
    first = loader.load(post, users, now=datetime.now(timezone.utc))
    assert first["accepted"] == first["events"] > 0 and first["duplicates"] == 0
    assert first["recompute"]["users"] == 12
    again = loader.load(post, users, now=datetime.now(timezone.utc))
    assert again["accepted"] == 0 and again["duplicates"] == again["events"]
    profile = api.get(f"/v1/apps/{APP}/users/lumen_282506_00009/features").json()
    by_feature = {f["feature"]: f["values"] for f in profile["features"]}
    assert set(by_feature) == {"ai_enhance", "background", "hd_export", "photo_import"}
    assert by_feature["ai_enhance"]["ai_enhance_uses_7d"] + by_feature["background"]["background_uses_7d"] >= 9

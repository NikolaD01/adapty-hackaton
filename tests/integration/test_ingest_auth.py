"""Optional SDK write key: off by default, enforced on events, features and event types when set."""

import pytest

from feature_signal.core.config import get_settings

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
FEATURE = {"key": "ai_generate", "name": "AI", "description": "d"}


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "k-123")
    get_settings.cache_clear()
    yield "k-123"
    get_settings.cache_clear()


def test_open_by_default(api):
    assert api.post(f"/v1/apps/{APP}/features", json=FEATURE).status_code == 200


def test_writes_need_the_key_when_set(api, key):
    assert api.post(f"/v1/apps/{APP}/features", json=FEATURE).status_code == 401
    assert api.post(f"/v1/apps/{APP}/features", json=FEATURE, headers={"X-Api-Key": key}).status_code == 200
    body = {
        "events": [
            {
                "event_id": "0b6f0c1e-5d1a-4c7e-9a0e-3f0f2b7c9a11",
                "customer_user_id": "u",
                "key": "x",
                "occurred_at": "2026-11-08T00:00:00Z",
            }
        ]
    }
    assert api.post(f"/v1/apps/{APP}/events", json=body).status_code == 401
    assert api.post(f"/v1/apps/{APP}/events", json=body, headers={"X-Api-Key": key}).status_code == 200


def test_reads_stay_open(api, key):
    assert api.get(f"/v1/apps/{APP}/features").status_code == 200

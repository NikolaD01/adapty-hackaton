"""Adapty webhook: verification, auth, mapping to events, idempotent retries, live net revenue."""

import pytest

from feature_signal.core.config import get_settings

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
URL = f"/v1/apps/{APP}/adapty-webhook"


def payload(event_type="subscription_started", user="lumen_282506_00007", net=8.5, pid="pe_1", **props):
    return {
        "profile_id": "prof-1",
        "customer_user_id": user,
        "event_type": event_type,
        "event_datetime": "2026-11-08T01:02:03.000000+0000",
        "event_api_version": 1,
        "attributions": {"network": "x"},
        "event_properties": {
            "profile_event_id": pid,
            "store": "app_store",
            "environment": "Sandbox",
            "vendor_product_id": "lumen.annual",
            "price_usd": 9.99,
            "net_revenue_usd": net,
            "transaction_id": "t1",
            "currency": "USD",
            "ab_test_name": "Main: 3 plans vs lifetime anchor (NA)",
            "profile_has_access_level": True,
            **props,
        },
    }


@pytest.fixture
def auth(monkeypatch):
    def set_auth(value: str) -> None:
        monkeypatch.setenv("ADAPTY_WEBHOOK_AUTH", value)
        get_settings.cache_clear()

    yield set_auth
    get_settings.cache_clear()


def test_verification_request_gets_an_empty_json(api):
    r = api.post(URL, json={})
    assert r.status_code == 200 and r.json() == {}


def test_purchase_becomes_an_event_with_signed_net_revenue(api):
    r = api.post(URL, json=payload())
    assert r.status_code == 200 and r.json() == {"accepted": 1, "duplicates": 0}
    item = api.get(f"/v1/apps/{APP}/users/lumen_282506_00007/timeline").json()["items"][0]
    assert item["key"] == "adapty_subscription_started"
    assert item["occurred_at"].startswith("2026-11-08T01:02:03")
    assert item["props"]["net_revenue_signed_usd"] == 8.5
    assert item["props"]["environment"] == "Sandbox"
    assert "attributions" not in item["props"]
    keys = [e["key"] for e in api.get(f"/v1/apps/{APP}/event-types").json()]
    assert "adapty_subscription_started" in keys


def test_retry_of_the_same_event_is_a_duplicate(api):
    api.post(URL, json=payload())
    assert api.post(URL, json=payload()).json() == {"accepted": 0, "duplicates": 1}


def test_net_revenue_rule_subtracts_refunds(api):
    api.post(URL, json=payload(net=8.5, pid="a"))
    api.post(URL, json=payload("subscription_renewed", net=8.5, pid="b"))
    api.post(URL, json=payload("subscription_refunded", net=8.5, pid="c"))
    api.post(URL, json=payload("trial_started", net=None, pid="d"))
    values = api.get(f"/v1/apps/{APP}/values", params={"rule_key": "adapty_net_revenue_90d"}).json()["items"]
    assert [(v["customer_user_id"], v["value"]) for v in values] == [("lumen_282506_00007", 8.5)]


def test_renamed_event_type_is_kept_safely(api):
    api.post(URL, json=payload("My Custom Event!", pid="z"))
    keys = [e["key"] for e in api.get(f"/v1/apps/{APP}/event-types").json()]
    assert "adapty_my_custom_event" in keys


def test_anonymous_profile_falls_back_to_profile_id(api):
    api.post(URL, json=payload(user=None, pid="anon"))
    assert api.get(f"/v1/apps/{APP}/users/adapty_profile:prof-1/timeline").json()["items"]


def test_authorization_header_is_checked_when_configured(api, auth):
    auth("secret-value")
    assert api.post(URL, json={}).status_code == 401
    assert api.post(URL, json={}, headers={"Authorization": "wrong"}).status_code == 401
    assert api.post(URL, json={}, headers={"Authorization": "secret-value"}).status_code == 200


def test_unusable_body_is_acknowledged_so_adapty_keeps_delivering(api):
    assert api.post(URL, json={"event_type": "subscription_started"}).status_code == 200

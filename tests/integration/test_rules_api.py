"""A6: rules API validates references against the catalog and round-trips every definition field."""

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
BASE = f"/v1/apps/{APP}"
RULE = {
    "key": "tokens_exhausted_7d",
    "name": "Ran out of tokens in 7 days",
    "description": "At least one AI event reported tokens_left <= 0",
    "source": "ai",
    "feature": "ai_generate",
    "definition": {
        "event_keys": ["generate_click"],
        "measure": "exists",
        "where": {"prop": "tokens_left", "op": "lte", "value": 0},
        "window_days": 7,
    },
}


def setup(api) -> None:
    api.post(f"{BASE}/features", json={"key": "ai_generate", "name": "AI", "description": "d"})
    for key in ("generate_click", "regenerate_click"):
        api.post(f"{BASE}/event-types", json={"key": key, "name": key, "description": "d", "features": ["ai_generate"]})


def test_save_and_list_a_rule_with_where(api):
    setup(api)
    r = api.post(f"{BASE}/rules", json=RULE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rule_id"] > 0 and body["source"] == "ai"
    assert body["definition"]["where"] == {"prop": "tokens_left", "op": "lte", "value": 0}
    keys = [x["key"] for x in api.get(f"{BASE}/rules").json()]
    assert "tokens_exhausted_7d" in keys and "ai_generate_uses_7d" in keys  # defaults from chapter 2


def test_ratio_rule_round_trips(api):
    setup(api)
    rule = {
        **RULE,
        "key": "regenerate_rate_7d",
        "definition": {
            "event_keys": ["regenerate_click"],
            "measure": "ratio",
            "denominator_event_keys": ["generate_click"],
            "window_days": 7,
        },
    }
    assert api.post(f"{BASE}/rules", json=rule).json()["definition"]["denominator_event_keys"] == ["generate_click"]


def test_unknown_event_key_is_refused(api):
    setup(api)
    rule = {**RULE, "definition": {**RULE["definition"], "event_keys": ["ghost"]}}
    r = api.post(f"{BASE}/rules", json=rule)
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_event_key"


def test_unknown_feature_is_refused(api):
    setup(api)
    r = api.post(f"{BASE}/rules", json={**RULE, "feature": "ghost"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_feature"


def test_saving_the_same_key_updates_it(api):
    setup(api)
    first = api.post(f"{BASE}/rules", json=RULE).json()
    second = api.post(f"{BASE}/rules", json={**RULE, "name": "Out of tokens"}).json()
    assert second["rule_id"] == first["rule_id"] and second["name"] == "Out of tokens"

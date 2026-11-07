"""A4: a user's last events, newest first by phone time."""

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
BASE = f"/v1/apps/{APP}"


def setup(api) -> None:
    api.post(f"{BASE}/features", json={"key": "ai_generate", "name": "AI", "description": "d"})
    for key in ("generate_click", "regenerate_click"):
        api.post(f"{BASE}/event-types", json={"key": key, "name": key, "description": "d", "features": ["ai_generate"]})


def ev(i: int, key: str, at: str, user: str = "u_42") -> dict:
    return {
        "event_id": f"00000000-0000-4000-8000-{i:012d}",
        "customer_user_id": user,
        "key": key,
        "occurred_at": at,
        "props": {"n": i},
    }


def test_timeline_is_newest_first_by_occurred_at(api):
    setup(api)
    api.post(
        f"{BASE}/events",
        json={
            "events": [
                ev(1, "generate_click", "2026-11-07T18:02:00Z"),
                ev(2, "regenerate_click", "2026-11-07T18:03:00Z"),
            ]
        },
    )
    api.post(f"{BASE}/events", json={"events": [ev(3, "generate_click", "2026-11-07T17:00:00Z")]})  # late
    body = api.get(f"{BASE}/users/u_42/timeline").json()
    assert body["customer_user_id"] == "u_42"
    assert [i["key"] for i in body["items"]] == ["regenerate_click", "generate_click", "generate_click"]
    assert body["items"][0]["props"] == {"n": 2}
    assert body["items"][0]["received_at"]


def test_timeline_limit_and_other_users_are_separate(api):
    setup(api)
    api.post(
        f"{BASE}/events",
        json={
            "events": [ev(i, "generate_click", f"2026-11-07T18:0{i}:00Z") for i in range(5)]
            + [ev(9, "generate_click", "2026-11-07T19:00:00Z", user="u_7")]
        },
    )
    items = api.get(f"{BASE}/users/u_42/timeline", params={"limit": 2}).json()["items"]
    assert [i["props"]["n"] for i in items] == [4, 3]
    assert api.get(f"{BASE}/users/nobody/timeline").json()["items"] == []
    assert api.get(f"{BASE}/users/u_42/timeline", params={"limit": 0}).status_code == 422

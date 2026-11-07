"""A3: idempotent ingest — duplicates never counted twice, counters move only for inserted rows."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from feature_signal.db.tables import EventRow, UserActionCountRow
from feature_signal.domain.models import SyncResult

APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
BASE = f"/v1/apps/{APP}"
E1 = "0b6f0c1e-5d1a-4c7e-9a0e-3f0f2b7c9a11"
E2 = "1c7f1d2f-6e2b-4d8f-8b1f-4a1f3c8d0b22"


def ev(event_id: str, key: str = "generate_click", user: str = "u_42", at: str = "2026-11-07T18:02:00Z", **props):
    return {"event_id": event_id, "customer_user_id": user, "key": key, "occurred_at": at, "props": props}


def setup_catalog(api) -> None:
    api.post(f"{BASE}/features", json={"key": "ai_generate", "name": "AI", "description": "d"})
    api.post(
        f"{BASE}/event-types",
        json={"key": "generate_click", "name": "g", "description": "d", "features": ["ai_generate"]},
    )


def db(db_url: str) -> Session:
    return Session(create_engine(db_url))


def counter(db_url: str, user: str = "u_42") -> int | None:
    with db(db_url) as s:
        return s.scalar(select(UserActionCountRow.n).where(UserActionCountRow.customer_user_id == user))


def test_event_is_stored_with_int_action_id_and_received_at(api, db_url):
    setup_catalog(api)
    r = api.post(f"{BASE}/events", json={"events": [ev(E1, tokens_used=40, tokens_left=0)]})
    assert r.status_code == 200, r.text
    assert r.json() == {"accepted": 1, "duplicates": 0, "unknown_keys": []}
    with db(db_url) as s:
        row = s.scalar(select(EventRow))
        assert isinstance(row.action_id, int)
        assert row.props == {"tokens_used": 40, "tokens_left": 0}
        assert row.received_at is not None
    assert counter(db_url) == 1


def test_same_event_id_twice_is_a_duplicate_and_the_counter_does_not_move(api, db_url):
    setup_catalog(api)
    api.post(f"{BASE}/events", json={"events": [ev(E1)]})
    r = api.post(f"{BASE}/events", json={"events": [ev(E1)]})
    assert r.json() == {"accepted": 0, "duplicates": 1, "unknown_keys": []}
    assert counter(db_url) == 1
    with db(db_url) as s:
        assert s.scalar(select(func.count()).select_from(EventRow)) == 1


def test_duplicate_inside_one_batch_counts_once(api, db_url):
    setup_catalog(api)
    r = api.post(f"{BASE}/events", json={"events": [ev(E1), ev(E1), ev(E2)]})
    assert r.json() == {"accepted": 2, "duplicates": 1, "unknown_keys": []}
    assert counter(db_url) == 2


def test_unknown_key_is_rejected_and_not_stored(api, db_url):
    setup_catalog(api)
    r = api.post(f"{BASE}/events", json={"events": [ev(E1, key="nope"), ev(E2)]})
    assert r.json() == {"accepted": 1, "duplicates": 0, "unknown_keys": ["nope"]}
    with db(db_url) as s:
        assert s.scalar(select(func.count()).select_from(EventRow)) == 1


def test_counter_keeps_the_latest_time_even_when_events_arrive_late(api, db_url):
    setup_catalog(api)
    api.post(f"{BASE}/events", json={"events": [ev(E1, at="2026-11-07T20:00:00Z")]})
    api.post(f"{BASE}/events", json={"events": [ev(E2, at="2026-11-07T10:00:00Z")]})  # buffered offline
    with db(db_url) as s:
        row = s.scalar(select(UserActionCountRow))
        assert row.n == 2
        assert row.last_ts.hour == 20


def test_free_text_prop_is_refused(api):
    setup_catalog(api)
    assert api.post(f"{BASE}/events", json={"events": [ev(E1, prompt="x" * 101)]}).status_code == 422


def test_more_than_500_events_is_refused(api):
    setup_catalog(api)
    batch = [ev(f"00000000-0000-4000-8000-{i:012d}") for i in range(501)]
    assert api.post(f"{BASE}/events", json={"events": batch}).status_code == 422


class RecordingSync:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.fail = fail

    async def sync_users(self, app_id, customer_user_ids):  # noqa: ANN001
        self.calls.append((app_id, list(customer_user_ids)))
        if self.fail:
            raise RuntimeError("adapty down")
        return SyncResult(checked=len(customer_user_ids), changed=0, attributes_written=0)


def test_membership_sync_runs_once_per_batch_after_commit(api, db_url):
    setup_catalog(api)
    sync = RecordingSync()
    api.app.state.membership_sync = sync
    api.post(f"{BASE}/events", json={"events": [ev(E1, user="u_1"), ev(E2, user="u_2")]})
    assert sync.calls == [(APP, ["u_1", "u_2"])]
    api.post(f"{BASE}/events", json={"events": [ev(E1, user="u_1")]})  # only a duplicate: nothing new
    assert len(sync.calls) == 1


def test_sync_failure_does_not_fail_ingest(api, db_url):
    setup_catalog(api)
    api.app.state.membership_sync = RecordingSync(fail=True)
    r = api.post(f"{BASE}/events", json={"events": [ev(E1)]})
    assert r.status_code == 200
    assert counter(db_url) == 1

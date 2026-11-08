"""C6: POST /v1/apps/{app_id}/lookup with a fake FlowLookup."""

import pytest
from fastapi.testclient import TestClient

from feature_signal.domain.models import ServedFlow
from feature_signal.main import create_app
from tests.conftest import LUMEN_APP_ID


class FakeLookup:
    def __init__(self):
        self.calls = []

    async def served(self, customer_user_id, placement):
        self.calls.append((customer_user_id, placement))
        in_segment = customer_user_id.endswith("7")
        return ServedFlow(
            customer_user_id,
            "hash-" + customer_user_id,
            "f-offer" if in_segment else "f-default",
            "Offer" if in_segment else "Default",
        )


@pytest.fixture
def lookup_client():
    app = create_app()
    app.state.flow_lookup = FakeLookup()
    return TestClient(app), app.state.flow_lookup


def test_lookup_returns_one_result_per_user(lookup_client):
    client, fake = lookup_client
    r = client.post(f"/v1/apps/{LUMEN_APP_ID}/lookup", json={"placement": "main", "customer_user_ids": ["u7", "u8"]})
    assert r.status_code == 200
    extra = {"audience_name": None, "ab_test_name": None, "arms": []}
    assert r.json()["results"] == [
        {"customer_user_id": "u7", "segment_hash": "hash-u7", "flow_id": "f-offer", "flow_name": "Offer", **extra},
        {"customer_user_id": "u8", "segment_hash": "hash-u8", "flow_id": "f-default", "flow_name": "Default", **extra},
    ]
    assert sorted(fake.calls) == [("u7", "main"), ("u8", "main")]


def test_lookup_returns_the_audience_and_the_arms_of_an_ab_test():
    from feature_signal.domain.models import FlowArm

    class AbLookup:
        async def served(self, customer_user_id, placement):
            arms = (FlowArm("f-c", "Main - 3 plans", 20, "control"), FlowArm("f-o", "Lifetime", 80, "offer"))
            return ServedFlow(customer_user_id, "h", "f-o", "Lifetime", "[fs] seg", "[fs] seg pr_1", arms)

    app = create_app()
    app.state.flow_lookup = AbLookup()
    body = (
        TestClient(app)
        .post(f"/v1/apps/{LUMEN_APP_ID}/lookup", json={"placement": "main", "customer_user_ids": ["u1"]})
        .json()["results"][0]
    )
    assert body["audience_name"] == "[fs] seg"
    assert body["ab_test_name"] == "[fs] seg pr_1"
    assert body["arms"] == [
        {"flow_id": "f-c", "flow_name": "Main - 3 plans", "weight": 20, "name": "control"},
        {"flow_id": "f-o", "flow_name": "Lifetime", "weight": 80, "name": "offer"},
    ]


def test_empty_user_list_is_422(lookup_client):
    client, _ = lookup_client
    r = client.post(f"/v1/apps/{LUMEN_APP_ID}/lookup", json={"placement": "main", "customer_user_ids": []})
    assert r.status_code == 422

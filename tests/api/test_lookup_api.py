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
    assert r.json()["results"] == [
        {"customer_user_id": "u7", "segment_hash": "hash-u7", "flow_id": "f-offer", "flow_name": "Offer"},
        {"customer_user_id": "u8", "segment_hash": "hash-u8", "flow_id": "f-default", "flow_name": "Default"},
    ]
    assert sorted(fake.calls) == [("u7", "main"), ("u8", "main")]


def test_empty_user_list_is_422(lookup_client):
    client, _ = lookup_client
    r = client.post(f"/v1/apps/{LUMEN_APP_ID}/lookup", json={"placement": "main", "customer_user_ids": []})
    assert r.status_code == 422

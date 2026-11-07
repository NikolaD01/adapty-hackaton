"""C6: served-flow lookup - profile read, variations URL and headers, results. No network."""

import hashlib

import httpx
import pytest

from feature_signal.core.errors import ApiError
from feature_signal.integrations.adapty.lookup import AdaptyFlowLookup
from feature_signal.services.lookup_service import LookupService

SECRET = "secret_live_PREFIX.restofkey"
PROFILE = {"data": {"profile_id": "pid-1", "segment_hash": "ef46db3751d8e999", "customer_user_id": "u1"}}
VARIATION = {"data": [{"flow_id": "f-main", "flow_name": "Main - 3 plans", "variation_id": "v1", "weight": 100}]}


def make_lookup(handler, **kwargs):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AdaptyFlowLookup(SECRET, http=http, **kwargs)


def router(profile=None, variations=None, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if "server-side-api/profile" in request.url.path:
            return profile or httpx.Response(200, json=PROFILE)
        return variations or httpx.Response(200, json=VARIATION)

    return handler


async def test_reads_segment_hash_from_the_profile():
    seen: list[httpx.Request] = []
    served = await make_lookup(router(seen=seen)).served("u1", "main")
    profile_request = seen[0]
    assert profile_request.method == "GET"
    assert profile_request.headers["adapty-customer-user-id"] == "u1"
    assert profile_request.headers["authorization"] == f"Api-Key {SECRET}"
    assert served.segment_hash == "ef46db3751d8e999"


async def test_variations_url_uses_key_prefix_placement_and_md5_of_placement_and_hash():
    seen: list[httpx.Request] = []
    await make_lookup(router(seen=seen)).served("u1", "main")
    request = seen[1]
    digest = hashlib.md5(b"main:ef46db3751d8e999").hexdigest()
    assert request.url.path == f"/api/v1/sdk/in-apps/secret_live_PREFIX/flow/variations/main/{digest}/"
    assert request.url.query == b"disable_cache"
    assert request.headers["authorization"] == f"Api-Key {SECRET}"
    assert request.headers["adapty-sdk-profile-id"] == "pid-1"
    assert request.headers["adapty-profile-segment-hash"] == "ef46db3751d8e999"
    assert request.headers["adapty-sdk-platform"] == "iOS"
    assert request.headers["adapty-sdk-version"]


async def test_returns_flow_id_and_name():
    served = await make_lookup(router()).served("u1", "main")
    assert (served.customer_user_id, served.flow_id, served.flow_name) == ("u1", "f-main", "Main - 3 plans")


async def test_no_variation_gives_flow_none():
    lookup = make_lookup(router(variations=httpx.Response(200, json={"data": []})))
    served = await lookup.served("u1", "main")
    assert served.flow_id is None
    assert served.flow_name is None
    assert served.segment_hash == "ef46db3751d8e999"


async def test_unknown_user_is_not_a_server_error():
    lookup = make_lookup(router(profile=httpx.Response(404, json={"errors": ["not found"]})))
    served = await lookup.served("ghost", "main")
    assert (served.segment_hash, served.flow_id, served.flow_name) == ("", None, None)


async def test_with_several_variations_the_heaviest_one_is_reported():
    data = {
        "data": [{"flow_id": "a", "flow_name": "A", "weight": 20}, {"flow_id": "b", "flow_name": "B", "weight": 80}]
    }
    served = await make_lookup(router(variations=httpx.Response(200, json=data))).served("u1", "main")
    assert served.flow_id == "b"


async def test_other_adapty_errors_surface_as_502_without_the_secret():
    lookup = make_lookup(router(profile=httpx.Response(401, text="bad key")))
    with pytest.raises(ApiError) as caught:
        await lookup.served("u1", "main")
    assert (caught.value.status, caught.value.code) == (502, "adapty_lookup_failed")
    assert SECRET not in caught.value.message + repr(caught.value.details)


async def test_service_returns_one_result_per_user_in_order():
    class Fake:
        async def served(self, customer_user_id, placement):
            from feature_signal.domain.models import ServedFlow

            return ServedFlow(customer_user_id, "h-" + customer_user_id, "flow-" + customer_user_id, "N")

    results = await LookupService(Fake()).lookup("main", ["b", "a", "c"])
    assert [r.customer_user_id for r in results] == ["b", "a", "c"]
    assert results[1].flow_id == "flow-a"

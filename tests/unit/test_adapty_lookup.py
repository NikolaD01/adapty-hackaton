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


HASH_ERROR = {"errors": [{"detail": "Incorrect segment hash", "status": "400", "code": "INCORRECT_SEGMENT_HASH_ERROR"}]}


def platform_router(good_platform: str, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        if "server-side-api/profile" in request.url.path:
            return httpx.Response(200, json=PROFILE)
        platform = request.headers["adapty-sdk-platform"]
        seen.append(platform)
        return (
            httpx.Response(200, json=VARIATION) if platform == good_platform else httpx.Response(400, json=HASH_ERROR)
        )

    return handler


async def test_an_android_user_is_found_by_retrying_with_the_android_platform():
    seen: list[str] = []
    served = await make_lookup(platform_router("Android", seen)).served("u1", "main")
    assert seen == ["iOS", "Android"]  # the platform is part of what Adapty validates the hash against
    assert served.flow_id == "f-main"


async def test_an_ios_user_needs_only_one_call():
    seen: list[str] = []
    await make_lookup(platform_router("iOS", seen)).served("u1", "main")
    assert seen == ["iOS"]


async def test_a_hash_that_no_platform_accepts_is_a_502_not_an_empty_answer():
    seen: list[str] = []
    with pytest.raises(ApiError) as caught:
        await make_lookup(platform_router("tvOS", seen)).served("u1", "main")
    assert (caught.value.status, caught.value.code) == (502, "adapty_lookup_failed")
    assert seen == ["iOS", "Android"]


async def test_other_400_errors_are_not_retried_with_another_platform():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "server-side-api/profile" in request.url.path:
            return httpx.Response(200, json=PROFILE)
        seen.append(request.headers["adapty-sdk-platform"])
        return httpx.Response(400, json={"errors": [{"code": "SOMETHING_ELSE"}]})

    with pytest.raises(ApiError):
        await make_lookup(handler).served("u1", "main")
    assert seen == ["iOS"]


AB_TEST = {
    "data": [
        {
            "flow_id": "f-control",
            "flow_name": "Main - 3 plans",
            "weight": 20,
            "variation_name": "control",
            "ab_test_name": "[fs] seg pr_1",
            "audience_name": "[fs] seg",
        },
        {
            "flow_id": "f-offer",
            "flow_name": "Main - Lifetime anchor",
            "weight": 80,
            "variation_name": "offer",
            "ab_test_name": "[fs] seg pr_1",
            "audience_name": "[fs] seg",
        },
    ]
}
DEFAULT = {
    "data": [
        {
            "flow_id": "f-main",
            "flow_name": "Main - 3 plans",
            "weight": 100,
            "variation_name": "Main - 3 plans",
            "ab_test_name": "Main - 3 plans",
            "audience_name": "All Users",
        }
    ]
}


async def test_a_user_in_an_ab_test_gets_both_arms_and_the_audience_not_a_guessed_arm():
    served = await make_lookup(router(variations=httpx.Response(200, json=AB_TEST))).served("u1", "main")
    assert served.audience_name == "[fs] seg"
    assert served.ab_test_name == "[fs] seg pr_1"
    assert [(a.flow_name, a.weight, a.name) for a in served.arms] == [
        ("Main - 3 plans", 20, "control"),
        ("Main - Lifetime anchor", 80, "offer"),
    ]
    assert served.flow_id == "f-offer"  # the largest arm; which arm the user sees is chosen by the SDK on the device


async def test_a_user_outside_any_test_has_one_flow_and_no_arms():
    served = await make_lookup(router(variations=httpx.Response(200, json=DEFAULT))).served("u1", "main")
    assert (served.flow_name, served.audience_name, served.ab_test_name, served.arms) == (
        "Main - 3 plans",
        "All Users",
        None,
        (),
    )

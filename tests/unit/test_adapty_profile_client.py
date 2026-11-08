"""C1: the attribute payload (list body, PATCH, headers), the limits and the retry rules - no network."""

import httpx
import pytest

from feature_signal.core.errors import ApiError
from feature_signal.integrations.adapty.profile_client import AdaptyProfileClient

SECRET = "secret_live_TESTKEY.abcdef"
PROFILE_URL = "https://api.adapty.io/api/v2/server-side-api/profile/"


def make_client(handler, **kwargs):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AdaptyProfileClient(SECRET, http=http, sleep=fake_sleep, **kwargs), sleeps


def recorder(*responses):
    """A handler that records requests and answers with the given responses in order (last one repeats)."""
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    return handler, seen


OK = httpx.Response(200, json={"data": {}})


async def test_write_sends_patch_with_a_list_body():
    handler, seen = recorder(OK)
    client, _ = make_client(handler)
    await client.write("lumen_282506_00007", {"p_segment": "power_editor", "f_ai_tier": "high"})
    (request,) = seen
    assert request.method == "PATCH"
    assert str(request.url) == PROFILE_URL
    assert request.headers["authorization"] == f"Api-Key {SECRET}"
    assert request.headers["adapty-customer-user-id"] == "lumen_282506_00007"
    payload = httpx.Response(200, content=request.content).json()
    assert isinstance(payload["custom_attributes"], list)  # a JSON object returns 400 at Adapty
    assert payload == {
        "custom_attributes": [
            {"key": "p_segment", "value": "power_editor"},
            {"key": "f_ai_tier", "value": "high"},
        ]
    }


async def test_none_is_sent_as_null_so_adapty_deletes_the_key():
    handler, seen = recorder(OK)
    client, _ = make_client(handler)
    await client.write("u1", {"p_segment": None})
    payload = httpx.Response(200, content=seen[0].content).json()
    assert payload == {"custom_attributes": [{"key": "p_segment", "value": None}]}


async def test_numbers_are_sent_as_numbers():
    handler, seen = recorder(OK)
    client, _ = make_client(handler)
    await client.write("u1", {"f_x_score": 0.82, "f_x_count": 7})
    payload = httpx.Response(200, content=seen[0].content).json()
    assert payload["custom_attributes"] == [
        {"key": "f_x_score", "value": 0.82},
        {"key": "f_x_count", "value": 7},
    ]


async def test_empty_attributes_send_nothing():
    handler, seen = recorder(OK)
    client, _ = make_client(handler)
    await client.write("u1", {})
    assert seen == []


@pytest.mark.parametrize(
    "attributes",
    [
        {"k" * 31: "x"},  # key too long
        {"": "x"},  # empty key
        {"bad key": "x"},  # space in key
        {"p_segment": "v" * 51},  # value too long
        {"p_flag": True},  # booleans are not a valid value
        {"p_n": float("nan")},  # not finite
        {f"k{i}": "x" for i in range(31)},  # 31 attributes
    ],
    ids=["key-31", "key-empty", "key-space", "value-51", "bool", "nan", "31-attributes"],
)
async def test_limits_are_checked_before_sending(attributes):
    handler, seen = recorder(OK)
    client, _ = make_client(handler)
    with pytest.raises(ApiError) as caught:
        await client.write("u1", attributes)
    assert (caught.value.status, caught.value.code) == (422, "attribute_limit")
    assert seen == []  # nothing reached Adapty


async def test_values_exactly_at_the_limits_are_accepted():
    handler, seen = recorder(OK)
    client, _ = make_client(handler)
    await client.write("u1", {"k" * 30: "v" * 50, **{f"k{i}": "x" for i in range(29)}})  # 30 attributes
    assert len(seen) == 1


async def test_empty_customer_user_id_is_refused():
    handler, seen = recorder(OK)
    client, _ = make_client(handler)
    with pytest.raises(ApiError) as caught:
        await client.write("", {"p_segment": "x"})
    assert caught.value.code == "invalid_customer_user_id"
    assert seen == []


async def test_429_is_retried_and_retry_after_is_honoured():
    handler, seen = recorder(httpx.Response(429, headers={"retry-after": "2"}), OK)
    client, sleeps = make_client(handler)
    await client.write("u1", {"p_segment": "x"})
    assert len(seen) == 2
    assert sleeps == [2.0]


async def test_5xx_is_retried_with_growing_delay_and_then_succeeds():
    handler, seen = recorder(httpx.Response(503), httpx.Response(502), OK)
    client, sleeps = make_client(handler, backoff_seconds=0.5)
    await client.write("u1", {"p_segment": "x"})
    assert len(seen) == 3
    assert sleeps == [0.5, 1.0]


async def test_a_network_error_is_retried():
    handler, seen = recorder(httpx.ConnectError("boom"), OK)
    client, _ = make_client(handler)
    await client.write("u1", {"p_segment": "x"})
    assert len(seen) == 2


async def test_gives_up_after_max_attempts_with_a_502():
    handler, seen = recorder(httpx.Response(503))
    client, sleeps = make_client(handler, max_attempts=3)
    with pytest.raises(ApiError) as caught:
        await client.write("u1", {"p_segment": "x"})
    assert (caught.value.status, caught.value.code) == (502, "adapty_unavailable")
    assert len(seen) == 3
    assert len(sleeps) == 2  # no sleep after the last attempt


async def test_a_400_is_not_retried_and_carries_adaptys_answer():
    body = {"errors": [{"source": "custom_attributes", "errors": ["value is not a valid list"]}]}
    handler, seen = recorder(httpx.Response(400, json=body))
    client, sleeps = make_client(handler)
    with pytest.raises(ApiError) as caught:
        await client.write("u1", {"p_segment": "x"})
    assert (caught.value.status, caught.value.code) == (502, "adapty_rejected")
    assert caught.value.details["status"] == 400
    assert "not a valid list" in caught.value.details["body"]
    assert len(seen) == 1
    assert sleeps == []


async def test_the_secret_never_appears_in_an_error():
    handler, _ = recorder(httpx.Response(401, text="Incorrect API key"))
    client, _ = make_client(handler)
    with pytest.raises(ApiError) as caught:
        await client.write("u1", {"p_segment": "x"})
    assert SECRET not in caught.value.message
    assert SECRET not in repr(caught.value.details)


async def test_missing_profile_explains_how_to_repair_the_connection():
    handler, seen = recorder(httpx.Response(404, json={"error_code": "profile_does_not_exist"}))
    client, sleeps = make_client(handler)
    with pytest.raises(ApiError) as caught:
        await client.write("lumen_282506_00007", {"p_segment": "power_editor"})
    assert caught.value.code == "adapty_profile_missing"
    assert caught.value.details["customer_user_id"] == "lumen_282506_00007"
    assert "configured Adapty app" in caught.value.message
    assert len(seen) == 1
    assert sleeps == []


@pytest.mark.parametrize("response", [httpx.Response(404, text="Not found"), httpx.Response(404, json={})])
async def test_an_unrelated_404_does_not_claim_the_profile_is_missing(response):
    handler, _ = recorder(response)
    client, _ = make_client(handler)
    with pytest.raises(ApiError) as caught:
        await client.write("u1", {"p_segment": "x"})
    assert caught.value.code == "adapty_rejected"

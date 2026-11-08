"""Demo repair creates only missing profiles and can safely be rerun."""

import importlib.util
import json
import subprocess
from pathlib import Path

import httpx
import pytest

from feature_signal.core.config import Settings

spec = importlib.util.spec_from_file_location(
    "seed_adapty_profiles", Path(__file__).parents[2] / "scripts" / "seed_adapty_profiles.py"
)
seeder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seeder)

APP = "test-adapty-app"
USER = {"i": 7, "platform": "Android", "country": "DE", "locale": "de_DE", "device": "Pixel 9"}
PROFILE = {
    "app_id": APP,
    "profile_id": "profile-7",
    "customer_user_id": "lumen_282506_00007",
    "total_revenue_usd": 0,
    "segment_hash": "hash",
    "timestamp": 1736425645861,
    "custom_attributes": [],
    "access_levels": [],
    "subscriptions": [],
    "non_subscriptions": [],
}


async def test_missing_demo_profile_is_created_once_with_its_original_identity():
    stored = {}
    posts = []

    def handler(request):
        user = request.headers["adapty-customer-user-id"]
        if request.method == "POST":
            posts.append(request)
            stored[user] = PROFILE
        if user not in stored:
            return httpx.Response(404, json={"error_code": "profile_does_not_exist"})
        return httpx.Response(200, json={"data": stored[user]})

    async with httpx.AsyncClient(base_url="https://api.adapty.io", transport=httpx.MockTransport(handler)) as http:
        assert await seeder.seed_profiles(http, [USER], APP) == {"created": 1, "existing": 0}
        assert await seeder.seed_profiles(http, [USER], APP) == {"created": 0, "existing": 1}
    assert len(posts) == 1
    assert posts[0].headers["adapty-customer-user-id"] == "lumen_282506_00007"
    assert posts[0].headers["adapty-platform"] == "Android"
    body = json.loads(posts[0].content)
    assert body["ip_country"] == "DE"
    assert body["installation_meta"]["platform"] == "Android"
    assert body["installation_meta"]["device_id"]
    assert body["analytics_disabled"] is True
    assert body["custom_attributes"] == [{"key": "fs_demo", "value": "lumen_282506"}]


@pytest.mark.parametrize("status", [401, 403, 404])
async def test_unrelated_read_errors_never_create_profiles(status):
    methods = []

    def handler(request):
        methods.append(request.method)
        return httpx.Response(status, json={"error_code": "other_error"})

    async with httpx.AsyncClient(base_url="https://api.adapty.io", transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(httpx.HTTPStatusError):
            await seeder.seed_profiles(http, [USER], APP)
    assert methods == ["GET"]


async def test_wrong_app_is_detected_before_processing_the_rest_of_the_dataset():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": {**PROFILE, "app_id": "different-app"}})

    async with httpx.AsyncClient(base_url="https://api.adapty.io", transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ValueError, match="ADAPTY_APP_ID"):
            await seeder.seed_profiles(http, [USER, {**USER, "i": 8}], APP)
    assert len(seen) == 1


async def test_invalid_platform_is_refused_before_any_profiles_are_written():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": PROFILE})

    async with httpx.AsyncClient(base_url="https://api.adapty.io", transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ValueError, match="platform"):
            await seeder.seed_profiles(http, [USER, {**USER, "i": 8, "platform": "wrong"}], APP)
    assert seen == []


@pytest.mark.parametrize("app_secret", ["different-secret", None])
def test_cli_preflight_refuses_wrong_credentials_before_seeding(monkeypatch, app_secret):
    settings = Settings(_env_file=None, adapty_app_id=APP, adapty_secret_key="configured-secret")

    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, json.dumps({"id": APP, "secret_key": app_secret}), "")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ValueError, match="ADAPTY_SECRET_KEY") as caught:
        seeder.verify_target_app(settings)
    assert "configured-secret" not in str(caught.value)
    assert "different-secret" not in str(caught.value)


def test_cli_preflight_checks_the_configured_app_and_key(monkeypatch):
    settings = Settings(_env_file=None, adapty_app_id=APP, adapty_secret_key="configured-secret")
    seen = []

    def run(args, **kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps({"id": APP, "secret_key": "configured-secret"}), "")

    monkeypatch.setattr(subprocess, "run", run)
    seeder.verify_target_app(settings)
    assert seen == [["adapty", "apps", "get", APP, "--json"]]

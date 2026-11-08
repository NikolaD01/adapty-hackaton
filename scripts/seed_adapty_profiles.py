"""Seed missing Lumen demo profiles in the configured Adapty app.

    python scripts/seed_adapty_profiles.py --users 5000

Uses ADAPTY_SECRET_KEY and ADAPTY_APP_ID from Settings. Existing profiles are left
untouched. New profiles carry the synthetic marker fs_demo and opt out of external
analytics. This creates identities, not purchases or subscription entitlements.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hmac
import json
import shlex
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from feature_signal.core.config import Settings, get_settings
from feature_signal.integrations.adapty.profile_client import PROFILE_PATH, RETRY_STATUSES


def verify_target_app(settings: Settings) -> None:
    """Verify the key against CLI app metadata before creating even the first profile."""
    try:
        result = subprocess.run(
            [*shlex.split(settings.adapty_cli), "apps", "get", settings.adapty_app_id, "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        app = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ValueError("Cannot verify the target app. Log in to the Adapty CLI and check ADAPTY_APP_ID.") from exc
    actual = app.get("secret_key")
    expected = settings.adapty_secret_key.get_secret_value()
    if app.get("id") != settings.adapty_app_id or not isinstance(actual, str) or not expected:
        raise ValueError("Cannot match ADAPTY_SECRET_KEY to ADAPTY_APP_ID; stopped before seeding")
    if not hmac.compare_digest(actual, expected):
        raise ValueError("ADAPTY_SECRET_KEY does not belong to ADAPTY_APP_ID; stopped before seeding")


async def _request(http: httpx.AsyncClient, method: str, **kwargs: Any) -> httpx.Response:
    for attempt in range(4):
        try:
            response = await http.request(method, PROFILE_PATH, **kwargs)
        except httpx.TransportError:
            if attempt == 3:
                raise
            delay = 0.5 * 2**attempt
        else:
            if response.status_code not in RETRY_STATUSES or attempt == 3:
                return response
            try:
                delay = min(30.0, max(0.0, float(response.headers["retry-after"])))
            except (KeyError, ValueError):
                delay = 0.5 * 2**attempt
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def seed_profiles(
    http: httpx.AsyncClient,
    users: list[dict[str, Any]],
    app_id: str,
    *,
    run_id: str = "282506",
    concurrency: int = 8,
    progress: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, int]:
    """Seed using a client whose credentials were checked by verify_target_app."""
    if not run_id.isascii() or not run_id.isdecimal():
        raise ValueError("run_id must contain decimal digits")
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    for user in users:
        if user.get("platform") not in ("iOS", "Android"):
            raise ValueError("Every demo user must have an iOS or Android platform")
        if type(user.get("i")) is not int or user["i"] < 0:
            raise ValueError("Every demo user must have a nonnegative integer index")
    counts = {"created": 0, "existing": 0}

    async def ensure(user: dict[str, Any]) -> str:
        customer_id = f"lumen_{run_id}_{user['i']:05d}"
        headers = {"adapty-customer-user-id": customer_id, "adapty-platform": user["platform"]}
        response = await _request(http, "GET", headers=headers)
        created = response.status_code == 404 and response.json().get("error_code") == "profile_does_not_exist"
        if created:
            meta = {key: user[key] for key in ("platform", "device", "locale", "os", "timezone") if key in user}
            meta["device_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{app_id}/{customer_id}"))
            body = {
                "installation_meta": meta,
                "analytics_disabled": True,
                "custom_attributes": [{"key": "fs_demo", "value": f"lumen_{run_id}"}],
            }
            if user.get("country"):
                body["ip_country"] = user["country"]
            response = await _request(http, "POST", headers=headers, json=body)
        response.raise_for_status()
        if response.json().get("data", {}).get("app_id") != app_id:
            raise ValueError("The API key's app does not match ADAPTY_APP_ID; stopped seeding")
        return "created" if created else "existing"

    if users:
        # Verify the key's app on the first result before processing the remaining users.
        counts[await ensure(users[0])] += 1
    for start in range(1, len(users), concurrency):
        outcomes = await asyncio.gather(*(ensure(user) for user in users[start : start + concurrency]))
        for result in outcomes:
            counts[result] += 1
        if progress and (start // 200 != (start + len(outcomes)) // 200 or start + len(outcomes) == len(users)):
            progress(dict(counts))
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=5000)
    parser.add_argument("--dataset", type=Path, default=Path("data/lumen_dataset.json.gz"))
    parser.add_argument("--run-id", default="282506")
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    if args.users < 1:
        parser.error("--users must be positive")
    settings = get_settings()
    secret = settings.adapty_secret_key.get_secret_value()
    if not secret:
        parser.error("Set ADAPTY_SECRET_KEY for the target demo app")
    verify_target_app(settings)
    with gzip.open(args.dataset, "rt") as stream:
        users = json.load(stream)["users"][: args.users]
    print(f"Seeding {len(users)} synthetic profiles in Adapty app {settings.adapty_app_id}", flush=True)
    async with httpx.AsyncClient(
        base_url=settings.adapty_api_base, headers={"Authorization": f"Api-Key {secret}"}, timeout=15.0
    ) as http:
        result = await seed_profiles(
            http,
            users,
            settings.adapty_app_id,
            run_id=args.run_id,
            concurrency=args.concurrency,
            progress=lambda counts: print(json.dumps(counts), flush=True),
        )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    asyncio.run(main())

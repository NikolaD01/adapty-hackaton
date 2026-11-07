"""C1 - Adapty server-side API: write custom attributes on one profile.

`PATCH /api/v2/server-side-api/profile/` with a LIST body (an object returns 400 "value is not a valid
list"). PATCH merges with the attributes already on the profile; a value of `None` is sent as JSON null
and deletes that key. Limits, all verified on 7 November: at most 30 attributes per profile, key up to
30 characters, value up to 50. We check them before sending, so a bad payload never reaches Adapty.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import httpx

from feature_signal.core.errors import ApiError

if TYPE_CHECKING:
    from feature_signal.core.config import Settings

MAX_ATTRIBUTES = 30
MAX_KEY_LENGTH = 30
MAX_VALUE_LENGTH = 50
PROFILE_PATH = "/api/v2/server-side-api/profile/"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_SECONDS = 30.0
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

AttributeValue = str | float | None


def _limit_error(message: str, **details: Any) -> ApiError:
    return ApiError(422, "attribute_limit", message, details)


def validate_attributes(attributes: dict[str, AttributeValue]) -> None:
    """Raise `ApiError(422, "attribute_limit")` if Adapty would refuse this payload."""
    if len(attributes) > MAX_ATTRIBUTES:
        raise _limit_error(f"At most {MAX_ATTRIBUTES} attributes per profile", count=len(attributes))
    for key, value in attributes.items():
        if not key or len(key) > MAX_KEY_LENGTH:
            raise _limit_error(f"Attribute key must be 1-{MAX_KEY_LENGTH} characters", key=key)
        if not _KEY_PATTERN.match(key):
            raise _limit_error("Attribute key may contain only letters, digits, '_', '-' and '.'", key=key)
        if value is None:
            continue  # null deletes the key
        if isinstance(value, bool):
            raise _limit_error("Attribute value must be a string or a number, not a boolean", key=key)
        if isinstance(value, str):
            if len(value) > MAX_VALUE_LENGTH:
                raise _limit_error(f"Attribute value must be at most {MAX_VALUE_LENGTH} characters", key=key)
        elif isinstance(value, int | float):
            if not math.isfinite(value):
                raise _limit_error("Attribute value must be a finite number", key=key)
        else:
            raise _limit_error("Attribute value must be a string, a number or None", key=key)


class AdaptyProfileClient:
    """Implements the `AttributeWriter` port over httpx."""

    def __init__(
        self,
        secret_key: str,
        *,
        base_url: str = "https://api.adapty.io",
        http: httpx.AsyncClient | None = None,
        max_attempts: int = 4,
        backoff_seconds: float = 0.5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._secret_key = secret_key
        self._url = base_url.rstrip("/") + PROFILE_PATH
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(timeout=10.0)
        self._max_attempts = max(1, max_attempts)
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings) -> AdaptyProfileClient:
        return cls(settings.adapty_secret_key.get_secret_value(), base_url=settings.adapty_api_base)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def write(self, customer_user_id: str, attributes: dict[str, AttributeValue]) -> None:
        if not customer_user_id:
            raise ApiError(422, "invalid_customer_user_id", "customer_user_id must not be empty")
        if not attributes:
            return
        validate_attributes(attributes)

        body = {"custom_attributes": [{"key": key, "value": value} for key, value in attributes.items()]}
        headers = {
            "Authorization": f"Api-Key {self._secret_key}",
            "adapty-customer-user-id": customer_user_id,
        }

        problem = "no response"
        for attempt in range(1, self._max_attempts + 1):
            retry_after: str | None = None
            try:
                response = await self._http.patch(self._url, json=body, headers=headers)
            except httpx.TransportError as exc:
                problem = f"network error ({type(exc).__name__})"
            else:
                if response.is_success:
                    return
                if response.status_code not in RETRY_STATUSES:
                    raise ApiError(
                        502,
                        "adapty_rejected",
                        f"Adapty rejected the attribute write (HTTP {response.status_code})",
                        {"status": response.status_code, "body": response.text[:300]},
                    )
                problem = f"HTTP {response.status_code}"
                retry_after = response.headers.get("retry-after")
            if attempt < self._max_attempts:
                await self._sleep(self._delay(attempt, retry_after))

        raise ApiError(
            502,
            "adapty_unavailable",
            f"Adapty did not accept the attribute write after {self._max_attempts} attempts ({problem})",
            {"attempts": self._max_attempts, "last_problem": problem},
        )

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), MAX_RETRY_AFTER_SECONDS)
            except ValueError:
                pass
        return self._backoff_seconds * 2 ** (attempt - 1)

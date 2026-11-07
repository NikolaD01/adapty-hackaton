"""C6 - which flow does Adapty serve to a user right now?

Two calls, both authenticated with the secret key:
1. `GET /api/v2/server-side-api/profile/` -> `profile_id` and `segment_hash` (changes when the user moves
   between segments, about 0.6 s after an attribute write).
2. `GET /api/v1/sdk/in-apps/<key prefix>/flow/variations/<placement>/<md5(placement:segment_hash)>/?disable_cache`
   -> the flow variation for that user. The SDK cache would serve the old flow, so the demo uses this.
Shape verified on 2026-11-08: a variation has `flow_id`, `flow_name`, `variation_id`, `weight`.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import httpx

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import ServedFlow

if TYPE_CHECKING:
    from feature_signal.core.config import Settings

SDK_VERSION = "3.15.0"
SDK_PLATFORM = "iOS"


class AdaptyFlowLookup:
    """Implements the `FlowLookup` port."""

    def __init__(
        self, secret_key: str, *, base_url: str = "https://api.adapty.io", http: httpx.AsyncClient | None = None
    ):
        self._secret_key = secret_key
        self._base = base_url.rstrip("/")
        self._key_prefix = secret_key.split(".")[0]
        self._http = http or httpx.AsyncClient(timeout=15.0)

    @classmethod
    def from_settings(cls, settings: Settings) -> AdaptyFlowLookup:
        return cls(settings.adapty_secret_key.get_secret_value(), base_url=settings.adapty_api_base)

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Api-Key {self._secret_key}"}

    @staticmethod
    def _failed(step: str, status: int) -> ApiError:
        return ApiError(
            502, "adapty_lookup_failed", f"Adapty {step} failed (HTTP {status})", {"step": step, "status": status}
        )

    async def served(self, customer_user_id: str, placement: str) -> ServedFlow:
        profile = await self._http.get(
            f"{self._base}/api/v2/server-side-api/profile/",
            headers={**self._auth(), "adapty-customer-user-id": customer_user_id},
        )
        if profile.status_code == 404:
            return ServedFlow(customer_user_id, "", None, None)
        if not profile.is_success:
            raise self._failed("profile read", profile.status_code)
        data = profile.json().get("data") or {}
        segment_hash = data.get("segment_hash") or ""
        profile_id = data.get("profile_id") or ""

        digest = hashlib.md5(f"{placement}:{segment_hash}".encode()).hexdigest()
        url = f"{self._base}/api/v1/sdk/in-apps/{self._key_prefix}/flow/variations/{placement}/{digest}/?disable_cache"
        variations = await self._http.get(
            url,
            headers={
                **self._auth(),
                "ADAPTY-SDK-PROFILE-ID": profile_id,
                "ADAPTY-PROFILE-SEGMENT-HASH": segment_hash,
                "ADAPTY-SDK-PLATFORM": SDK_PLATFORM,
                "ADAPTY-SDK-VERSION": SDK_VERSION,
            },
        )
        if not variations.is_success:
            raise self._failed("flow lookup", variations.status_code)
        items: list[dict[str, Any]] = [v for v in (variations.json().get("data") or []) if isinstance(v, dict)]
        if not items:
            return ServedFlow(customer_user_id, segment_hash, None, None)
        top = max(items, key=lambda v: v.get("weight") or 0)
        return ServedFlow(customer_user_id, segment_hash, top.get("flow_id"), top.get("flow_name"))

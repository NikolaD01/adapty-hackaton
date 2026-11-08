"""Optional write key for the SDK (owner A). Off unless INGEST_API_KEY is set, so local demos stay open."""

import hmac
from typing import Annotated

from fastapi import Header

from feature_signal.core.config import get_settings
from feature_signal.core.errors import ApiError


def require_ingest_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().ingest_api_key.get_secret_value()
    if expected and not hmac.compare_digest(x_api_key or "", expected):
        raise ApiError(401, "unauthorized", "missing or wrong X-Api-Key")

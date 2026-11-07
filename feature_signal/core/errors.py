"""Error shape shared by every endpoint: {"error": {"code", "message", "details"}}."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def not_implemented(what: str) -> ApiError:
    """Routes that exist in the contract but are not built yet return 501 (the dashboard shows 'coming soon')."""
    return ApiError(501, "not_implemented", f"{what} is not implemented yet")


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    body = {"error": {"code": exc.code, "message": exc.message, "details": exc.details}}
    return JSONResponse(status_code=exc.status, content=body)

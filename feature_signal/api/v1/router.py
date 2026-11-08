"""Mounts every area's router under /v1. Shared file: contract-change."""

from fastapi import APIRouter

from feature_signal.api.v1 import (
    adapty_webhook,
    catalog,
    decisions,
    events,
    insights,
    lookup,
    membership,
    proposals,
    rules,
    settings,
    values,
)

api_router = APIRouter(prefix="/v1")


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


for module in (
    adapty_webhook,
    catalog,
    events,
    rules,
    values,
    insights,
    proposals,
    settings,
    decisions,
    lookup,
    membership,
):
    api_router.include_router(module.router)

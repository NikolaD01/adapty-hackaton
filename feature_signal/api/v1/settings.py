"""Mode settings routes (owner C)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.proposals import AppSettings

router = APIRouter(tags=["settings (C)"])


@router.get("/apps/{app_id}/settings", response_model=AppSettings)
async def get_app_settings(app_id: str) -> AppSettings:
    raise not_implemented("get_app_settings")


@router.put("/apps/{app_id}/settings", response_model=AppSettings)
async def put_app_settings(app_id: str, body: AppSettings) -> AppSettings:
    raise not_implemented("put_app_settings")

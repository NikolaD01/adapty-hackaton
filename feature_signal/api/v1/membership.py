"""Fast loop: keep Adapty attributes in step with users' values (owner C)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.proposals import MembershipSyncIn, MembershipSyncOut

router = APIRouter(tags=["membership (C)"])


@router.post("/apps/{app_id}/membership:sync", response_model=MembershipSyncOut)
async def sync_membership(app_id: str, body: MembershipSyncIn) -> MembershipSyncOut:
    raise not_implemented("sync_membership")

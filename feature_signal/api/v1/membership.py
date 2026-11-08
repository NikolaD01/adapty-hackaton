"""Fast loop: keep Adapty attributes in step with users' values (owner C)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.config import get_settings
from feature_signal.db.session import get_session
from feature_signal.domain.ports import AttributeWriter
from feature_signal.integrations.adapty.profile_client import AdaptyProfileClient
from feature_signal.schemas.proposals import MembershipSyncIn, MembershipSyncOut
from feature_signal.services.membership_service import build_membership_service

router = APIRouter(tags=["membership (C)"])
Session = Annotated[AsyncSession, Depends(get_session)]


def get_attribute_writer(request: Request) -> AttributeWriter:
    """`app.state.attribute_writer` if set (tests), otherwise the real Adapty client, built once."""
    writer = getattr(request.app.state, "attribute_writer", None)
    if writer is None:
        writer = AdaptyProfileClient.from_settings(get_settings())
        request.app.state.attribute_writer = writer
    return writer


@router.post("/apps/{app_id}/membership:sync", response_model=MembershipSyncOut)
async def sync_membership(
    app_id: str,
    body: MembershipSyncIn,
    session: Session,
    writer: Annotated[AttributeWriter, Depends(get_attribute_writer)],
) -> MembershipSyncOut:
    service = build_membership_service(session, writer)
    try:
        result = await service.sync_users(app_id, body.customer_user_ids)
    finally:
        await session.commit()
    return MembershipSyncOut(
        checked=result.checked, changed=result.changed, attributes_written=result.attributes_written
    )

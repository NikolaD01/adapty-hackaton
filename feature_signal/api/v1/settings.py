"""Mode settings routes (owner C)."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.api.v1.proposals import autopilot_job
from feature_signal.db.session import get_session
from feature_signal.schemas.proposals import AppSettings
from feature_signal.services.proposal_service import ProposalService

router = APIRouter(tags=["settings (C)"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/apps/{app_id}/settings", response_model=AppSettings)
async def get_app_settings(app_id: str, session: Session) -> AppSettings:
    return await ProposalService(session).get_settings(app_id)


@router.put("/apps/{app_id}/settings", response_model=AppSettings)
async def put_app_settings(
    app_id: str, body: AppSettings, session: Session, request: Request, background: BackgroundTasks
) -> AppSettings:
    """Save the mode. Switching to autopilot launches the waiting drafts after the answer (within the limits)."""
    saved = await ProposalService(session).put_settings(app_id, body)
    if saved.mode == "autopilot":
        background.add_task(autopilot_job(request, app_id))
    return saved

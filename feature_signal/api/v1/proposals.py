"""Proposal lifecycle and paywall draft routes (owner C)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.errors import not_implemented
from feature_signal.db.session import get_session
from feature_signal.schemas.proposals import (
    PaywallDraftIn,
    PaywallDraftOut,
    ProposalOut,
    ProposalPatch,
    ProposalsIn,
    ProposalStatus,
    RejectIn,
)
from feature_signal.services.proposal_service import ProposalService

router = APIRouter(tags=["proposals (C)"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/apps/{app_id}/proposals", response_model=list[ProposalOut])
async def list_proposals(app_id: str, session: Session, status: ProposalStatus | None = None) -> list[ProposalOut]:
    return await ProposalService(session).list(app_id, status)


@router.post("/apps/{app_id}/proposals", response_model=list[ProposalOut])
async def create_proposals(app_id: str, body: ProposalsIn, session: Session) -> list[ProposalOut]:
    return await ProposalService(session).create(app_id, body.proposals)


@router.patch("/proposals/{proposal_id}", response_model=ProposalOut)
async def edit_proposal(proposal_id: str, body: ProposalPatch, session: Session) -> ProposalOut:
    return await ProposalService(session).patch(proposal_id, body)


@router.post("/proposals/{proposal_id}:approve", response_model=ProposalOut)
async def approve_proposal(proposal_id: str) -> ProposalOut:
    raise not_implemented("approve_proposal")


@router.post("/proposals/{proposal_id}:reject", response_model=ProposalOut)
async def reject_proposal(proposal_id: str, body: RejectIn, session: Session) -> ProposalOut:
    return await ProposalService(session).reject(proposal_id, body.reason)


@router.post("/proposals/{proposal_id}/paywall-draft", response_model=PaywallDraftOut)
async def paywall_draft(proposal_id: str, body: PaywallDraftIn) -> PaywallDraftOut:
    raise not_implemented("paywall_draft")

"""Proposal lifecycle and paywall draft routes (owner C)."""

from fastapi import APIRouter

from feature_signal.core.errors import not_implemented
from feature_signal.schemas.proposals import (
    PaywallDraftIn,
    PaywallDraftOut,
    ProposalOut,
    ProposalPatch,
    ProposalsIn,
    ProposalStatus,
    RejectIn,
)

router = APIRouter(tags=["proposals (C)"])


@router.get("/apps/{app_id}/proposals", response_model=list[ProposalOut])
async def list_proposals(app_id: str, status: ProposalStatus | None = None) -> list[ProposalOut]:
    raise not_implemented("list_proposals")


@router.post("/apps/{app_id}/proposals", response_model=list[ProposalOut])
async def create_proposals(app_id: str, body: ProposalsIn) -> list[ProposalOut]:
    raise not_implemented("create_proposals")


@router.patch("/proposals/{proposal_id}", response_model=ProposalOut)
async def edit_proposal(proposal_id: str, body: ProposalPatch) -> ProposalOut:
    raise not_implemented("edit_proposal")


@router.post("/proposals/{proposal_id}:approve", response_model=ProposalOut)
async def approve_proposal(proposal_id: str) -> ProposalOut:
    raise not_implemented("approve_proposal")


@router.post("/proposals/{proposal_id}:reject", response_model=ProposalOut)
async def reject_proposal(proposal_id: str, body: RejectIn) -> ProposalOut:
    raise not_implemented("reject_proposal")


@router.post("/proposals/{proposal_id}/paywall-draft", response_model=PaywallDraftOut)
async def paywall_draft(proposal_id: str, body: PaywallDraftIn) -> PaywallDraftOut:
    raise not_implemented("paywall_draft")

"""Proposal lifecycle and paywall draft routes (owner C)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.api.v1.membership import get_attribute_writer
from feature_signal.core.config import get_settings
from feature_signal.core.errors import not_implemented
from feature_signal.db.session import SessionFactory, get_session
from feature_signal.domain.ports import AttributeWriter, MembershipSync
from feature_signal.integrations.adapty.cli import AdaptyCommands, SubprocessAdaptyCli
from feature_signal.schemas.proposals import (
    PaywallDraftIn,
    PaywallDraftOut,
    ProposalOut,
    ProposalPatch,
    ProposalsIn,
    ProposalStatus,
    RejectIn,
)
from feature_signal.services.activation_service import ActivationService
from feature_signal.services.membership_service import SqlMembershipSync
from feature_signal.services.proposal_service import ProposalService

router = APIRouter(tags=["proposals (C)"])
Session = Annotated[AsyncSession, Depends(get_session)]


def get_adapty_commands(request: Request) -> AdaptyCommands:
    """`app.state.adapty_commands` if set (tests), otherwise the real CLI for the configured Adapty app."""
    commands = getattr(request.app.state, "adapty_commands", None)
    if commands is None:
        settings = get_settings()
        commands = AdaptyCommands(SubprocessAdaptyCli(settings.adapty_cli), settings.adapty_app_id)
        request.app.state.adapty_commands = commands
    return commands


def get_membership_sync(
    request: Request, writer: Annotated[AttributeWriter, Depends(get_attribute_writer)]
) -> MembershipSync:
    """`app.state.membership_sync` if wired (main.py or tests), otherwise built here from the real writer."""
    sync = getattr(request.app.state, "membership_sync", None)
    return sync if sync is not None else SqlMembershipSync(SessionFactory, writer)


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
async def approve_proposal(
    proposal_id: str,
    session: Session,
    commands: Annotated[AdaptyCommands, Depends(get_adapty_commands)],
    membership: Annotated[MembershipSync, Depends(get_membership_sync)],
) -> ProposalOut:
    return await ActivationService(session, commands, membership).approve(proposal_id, decided_by="human")


@router.post("/proposals/{proposal_id}:reject", response_model=ProposalOut)
async def reject_proposal(proposal_id: str, body: RejectIn, session: Session) -> ProposalOut:
    return await ProposalService(session).reject(proposal_id, body.reason)


@router.post("/proposals/{proposal_id}/paywall-draft", response_model=PaywallDraftOut)
async def paywall_draft(proposal_id: str, body: PaywallDraftIn) -> PaywallDraftOut:
    raise not_implemented("paywall_draft")

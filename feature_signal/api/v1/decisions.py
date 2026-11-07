"""Decision log routes (owner C)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.db.session import get_session
from feature_signal.repositories.decisions import DecisionRepository
from feature_signal.schemas.proposals import DecisionOut, DecisionStep

router = APIRouter(tags=["decisions (C)"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/apps/{app_id}/decisions", response_model=list[DecisionOut])
async def list_decisions(app_id: str, session: Session, proposal_id: str | None = None) -> list[DecisionOut]:
    """Newest first. `?proposal_id=` narrows it to one proposal (extra, optional)."""
    rows = await DecisionRepository(session).list(app_id, proposal_id)
    return [
        DecisionOut(
            decision_id=r.decision_id,
            proposal_id=r.proposal_id,
            decided_by=r.decided_by,
            action=r.action,
            steps=[DecisionStep(**s) for s in r.steps or []],
            at=r.at,
        )
        for r in rows
    ]

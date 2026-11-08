"""C7 - autopilot: approve drafts by itself, inside the limits, and never publish a flow.

Autopilot is plain code, no model call. For every draft (most valuable first) it runs the same activation as a human
approve, with `decided_by="autopilot"`, as long as fewer than `max_live_proposals` proposals are running. A holdout
below `min_holdout_pct` is raised to it (recorded in `edits`). A proposal that is live, executing or waiting for a
human publish uses a slot; a failed one does not. Publishing a flow is not reachable from here: a new AI paywall
stays `awaiting_publish` for one human click, then the test starts.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.domain.models import ProposalDraft
from feature_signal.schemas.proposals import ProposalOut, ProposalPatch
from feature_signal.services.activation_service import ActivationService
from feature_signal.services.proposal_service import ProposalService

OCCUPYING_STATUSES = frozenset({"live", "executing", "awaiting_publish"})


class AutopilotService:
    def __init__(self, session: AsyncSession, activation: ActivationService) -> None:
        self._proposals = ProposalService(session)
        self._activation = activation

    async def run(self, app_id: str) -> list[ProposalOut]:
        settings = await self._proposals.get_settings(app_id)
        if settings.mode != "autopilot":
            return []
        limits = settings.autopilot
        occupied = sum(1 for p in await self._proposals.list(app_id) if p.status in OCCUPYING_STATUSES)
        drafts = sorted(await self._proposals.list(app_id, "draft"), key=lambda p: -p.expected_effect.diff)
        results: list[ProposalOut] = []
        for draft in drafts:
            if occupied >= limits.max_live_proposals:
                break
            if draft.holdout_pct < limits.min_holdout_pct:
                await self._proposals.patch(draft.proposal_id, ProposalPatch(holdout_pct=limits.min_holdout_pct))
            outcome = await self._activation.approve(draft.proposal_id, decided_by="autopilot")
            results.append(outcome)
            if outcome.status in OCCUPYING_STATUSES:
                occupied += 1
        return results


class AutopilotSink:
    """`ProposalSink` for B in autopilot deployments: store the drafts, then let autopilot launch them."""

    def __init__(self, session: AsyncSession, autopilot: AutopilotService) -> None:
        self._proposals = ProposalService(session)
        self._autopilot = autopilot

    async def create_many(self, app_id: str, drafts: Sequence[ProposalDraft]) -> list[str]:
        ids = await self._proposals.create_many(app_id, drafts)
        await self._autopilot.run(app_id)
        return ids

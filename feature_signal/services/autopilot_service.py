"""C7 - autopilot: approve drafts by itself, inside the limits, and never publish a flow.

Autopilot is plain code, no model call. For every draft (most valuable first) it runs the same activation as a human
approve, with `decided_by="autopilot"`, as long as fewer than `max_live_proposals` proposals are running. A holdout
below `min_holdout_pct` is raised to it (recorded in `edits`). A proposal that is live, executing or waiting for a
human publish uses a slot; a failed one does not. Publishing a flow is not reachable from here: a new AI paywall
stays `awaiting_publish` for one human click, then the test starts.

`allowed_placements` (optional) limits autopilot to those trigger placements; a draft for any other placement is left
for a human. The demo uses it to keep autopilot on the test placement `fs_test`, away from the app's real placements.
Autopilot runs when drafts are created in autopilot mode and when the mode is switched to autopilot.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from collections.abc import Awaitable, Callable, Collection, Coroutine, Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.domain.models import ProposalDraft
from feature_signal.schemas.proposals import ProposalOut, ProposalPatch
from feature_signal.services.activation_service import ActivationService
from feature_signal.services.proposal_service import ProposalService

log = logging.getLogger(__name__)

OCCUPYING_STATUSES = frozenset({"live", "executing", "awaiting_publish"})

ActivationFactory = Callable[[AsyncSession], ActivationService]
SessionFactory = Callable[[], Any]  # an async_sessionmaker: `async with factory() as session`


class AutopilotService:
    def __init__(
        self,
        session: AsyncSession,
        activation: ActivationService,
        *,
        allowed_placements: Collection[str] | None = None,
    ) -> None:
        self._proposals = ProposalService(session)
        self._activation = activation
        self._allowed = frozenset(allowed_placements) if allowed_placements is not None else None

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
            if self._allowed is not None and draft.trigger_placement not in self._allowed:
                continue  # not a placement autopilot may change: the draft waits for a human
            if draft.holdout_pct < limits.min_holdout_pct:
                await self._proposals.patch(draft.proposal_id, ProposalPatch(holdout_pct=limits.min_holdout_pct))
            outcome = await self._activation.approve(draft.proposal_id, decided_by="autopilot")
            results.append(outcome)
            if outcome.status in OCCUPYING_STATUSES:
                occupied += 1
        return results


async def run_autopilot(
    session_factory: SessionFactory,
    activation_factory: ActivationFactory,
    app_id: str,
    allowed_placements: Collection[str] | None = None,
) -> list[ProposalOut]:
    """One autopilot pass in its own session, for work that outlives the request (mode switch, insight run)."""
    try:
        async with session_factory() as session:
            service = AutopilotService(session, activation_factory(session), allowed_placements=allowed_placements)
            return await service.run(app_id)
    except Exception:  # noqa: BLE001 - a background pass must log, not vanish
        log.exception("Autopilot pass for %s failed", app_id)
        return []


_background: set[asyncio.Task[Any]] = set()


def spawn(coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    """Run in the background and keep a reference until done (a bare task can be garbage-collected)."""
    task = asyncio.get_running_loop().create_task(coroutine)
    _background.add(task)
    task.add_done_callback(_background.discard)
    return task


class AutopilotSink:
    """`ProposalSink` for B in autopilot deployments: store the drafts, then let autopilot launch them."""

    def __init__(self, session: AsyncSession, autopilot: AutopilotService) -> None:
        self._proposals = ProposalService(session)
        self._autopilot = autopilot

    async def create_many(self, app_id: str, drafts: Sequence[ProposalDraft]) -> list[str]:
        ids = await self._proposals.create_many(app_id, drafts)
        await self._autopilot.run(app_id)
        return ids


class LaunchingSink:
    """`ProposalSink` for B in the running app: store the drafts, then start an autopilot pass in the background.

    The insight run returns as soon as the drafts are stored; in human mode the pass does nothing. `placement_map`
    moves drafts to another trigger placement before they are stored (the demo sends `main` to the test placement).
    """

    def __init__(
        self,
        session: AsyncSession,
        launch: Callable[[str], Awaitable[Any]],
        *,
        placement_map: Mapping[str, str] | None = None,
        schedule: Callable[[Coroutine[Any, Any, Any]], Any] = spawn,
    ) -> None:
        self._proposals = ProposalService(session)
        self._launch = launch
        self._map = dict(placement_map or {})
        self._schedule = schedule

    async def create_many(self, app_id: str, drafts: Sequence[ProposalDraft]) -> list[str]:
        """Store only drafts that are new: a repeated insight run must not queue the same offer twice."""
        moved = [
            dataclasses.replace(d, trigger_placement=self._map.get(d.trigger_placement, d.trigger_placement))
            for d in drafts
        ]
        known = {
            (p.segment_key, p.trigger_placement, p.action.flow_id): p.proposal_id
            for p in await self._proposals.list(app_id)
            if p.status not in ("rejected", "failed")
        }
        fresh = [d for d in moved if (d.segment_key, d.trigger_placement, d.flow_id) not in known]
        created = iter(await self._proposals.create_many(app_id, fresh) if fresh else [])
        ids = [known.get((d.segment_key, d.trigger_placement, d.flow_id)) or next(created) for d in moved]
        self._schedule(self._launch(app_id))
        return ids

"""C3 - proposal lifecycle: store drafts from B, edit, reject, settings. Also the state machine C4 uses.

Implements the `ProposalSink` port (B hands drafts to C). Approve / activation is C4.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.errors import ApiError
from feature_signal.db.tables import ProposalRow
from feature_signal.domain.models import ProposalDraft
from feature_signal.repositories.decisions import DecisionRepository
from feature_signal.repositories.proposals import ProposalRepository, SettingsRepository
from feature_signal.schemas.proposals import (
    AdaptyFilter,
    AdaptyRefs,
    AppSettings,
    ExpectedEffect,
    ProposalAction,
    ProposalCondition,
    ProposalEdit,
    ProposalIn,
    ProposalOut,
    ProposalPatch,
)

# docs/contracts/api.md: draft -> approved -> executing -> live | failed; draft -> rejected;
# executing -> awaiting_publish -> live (a new AI paywall waits for a human publish, also in autopilot).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved", "rejected"},
    "approved": {"executing"},
    "executing": {"live", "failed", "awaiting_publish"},
    "awaiting_publish": {"live", "failed"},
}


def check_transition(src: str, dst: str) -> None:
    if dst not in ALLOWED_TRANSITIONS.get(src, set()):
        raise ApiError(
            409, "invalid_transition", f"A proposal cannot go from '{src}' to '{dst}'", {"from": src, "to": dst}
        )


def draft_to_input(draft: ProposalDraft) -> ProposalIn:
    return ProposalIn(
        trigger_placement=draft.trigger_placement,
        segment_key=draft.segment_key,
        condition=ProposalCondition(
            attribute=draft.condition.field, op=draft.condition.op, value=draft.condition.value
        ),
        adapty_filters=[AdaptyFilter(field=c.field, op=c.op, value=c.value) for c in draft.adapty_filters],
        action=ProposalAction(
            flow_id=draft.flow_id,
            flow_name=draft.flow_name,
            highlight_feature=draft.highlight_feature,
            needs_publish=draft.needs_publish,
        ),
        holdout_pct=draft.holdout_pct,
        cooldown_days=draft.cooldown_days,
        expected_effect=ExpectedEffect(diff=draft.expected_diff, ci_low=draft.ci_low, ci_high=draft.ci_high),
        reason=draft.reason,
        evidence=draft.evidence,
        created_by="ai",
    )


def to_out(row: ProposalRow) -> ProposalOut:
    return ProposalOut(
        proposal_id=row.proposal_id,
        app_id=row.app_id,
        status=row.status,
        created_by=row.created_by,
        decided_by=row.decided_by,
        mode_at_decision=row.mode_at_decision,
        trigger_placement=row.trigger_placement,
        segment_key=row.segment_key,
        condition=ProposalCondition(**row.condition),
        adapty_filters=[AdaptyFilter(**f) for f in row.adapty_filters or []],
        action=ProposalAction(**row.action),
        holdout_pct=row.holdout_pct,
        cooldown_days=row.cooldown_days,
        expected_effect=ExpectedEffect(**row.expected_effect),
        reason=row.reason,
        evidence=row.evidence or {},
        edits=[ProposalEdit.model_validate(e) for e in row.edits or []],
        adapty=AdaptyRefs(**(row.adapty or {})),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ProposalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.proposals = ProposalRepository(session)
        self.decisions = DecisionRepository(session)
        self.settings = SettingsRepository(session)

    # --- reads / creation -----------------------------------------------------------------------
    async def list(self, app_id: str, status: str | None = None) -> list[ProposalOut]:
        return [to_out(r) for r in await self.proposals.list(app_id, status)]

    async def create(self, app_id: str, items: Sequence[ProposalIn]) -> list[ProposalOut]:
        now = datetime.now(timezone.utc)
        rows = []
        for item in items:
            row = ProposalRow(
                proposal_id=f"pr_{uuid4().hex[:10]}",
                app_id=app_id,
                status="draft",
                created_by=item.created_by,
                trigger_placement=item.trigger_placement,
                segment_key=item.segment_key,
                condition=item.condition.model_dump(mode="json"),
                adapty_filters=[f.model_dump(mode="json") for f in item.adapty_filters],
                action=item.action.model_dump(mode="json"),
                holdout_pct=item.holdout_pct,
                cooldown_days=item.cooldown_days,
                expected_effect=item.expected_effect.model_dump(mode="json"),
                reason=item.reason,
                evidence=item.evidence,
                edits=[],
                adapty=AdaptyRefs().model_dump(),
                created_at=now,
                updated_at=now,
            )
            rows.append(await self.proposals.add(row))
        await self.session.commit()
        return [to_out(r) for r in rows]

    async def create_many(self, app_id: str, drafts: Sequence[ProposalDraft]) -> list[str]:
        """`ProposalSink` port: B hands its drafts here."""
        created = await self.create(app_id, [draft_to_input(d) for d in drafts])
        return [p.proposal_id for p in created]

    async def _get(self, proposal_id: str) -> ProposalRow:
        row = await self.proposals.get(proposal_id)
        if row is None:
            raise ApiError(404, "proposal_not_found", f"No proposal '{proposal_id}'")
        return row

    # --- human edit -----------------------------------------------------------------------------
    async def patch(self, proposal_id: str, patch: ProposalPatch) -> ProposalOut:
        row = await self._get(proposal_id)
        if row.status != "draft":
            raise ApiError(409, "proposal_not_editable", "Only a draft proposal can be edited", {"status": row.status})
        changes = patch.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)
        edits = list(row.edits or [])
        action, condition = dict(row.action), dict(row.condition)

        def record(field: str, old: Any, new: Any) -> None:
            if old != new:
                edits.append({"at": now.isoformat(), "field": field, "from": old, "to": new})

        for field, new in changes.items():
            if field == "flow_id":
                record(field, action.get("flow_id"), new)
                action["flow_id"] = new
            elif field == "condition_value":
                record(field, condition.get("value"), new)
                condition["value"] = new
            else:  # holdout_pct, cooldown_days, trigger_placement are columns
                record(field, getattr(row, field), new)
                setattr(row, field, new)
        row.action, row.condition, row.edits = action, condition, edits
        row.updated_at = now
        await self.session.commit()
        return to_out(row)

    # --- reject ---------------------------------------------------------------------------------
    async def reject(self, proposal_id: str, reason: str) -> ProposalOut:
        row = await self._get(proposal_id)
        check_transition(row.status, "rejected")
        mode = (await self.settings.get(row.app_id)).mode
        row.status, row.decided_by, row.mode_at_decision = "rejected", "human", mode
        row.updated_at = datetime.now(timezone.utc)
        await self.decisions.add(
            row.app_id,
            row.proposal_id,
            "human",
            "reject",
            [{"step": "reject", "ok": True, "detail": {"reason": reason}}],
        )
        await self.session.commit()
        return to_out(row)

    # --- settings -------------------------------------------------------------------------------
    async def get_settings(self, app_id: str) -> AppSettings:
        return await self.settings.get(app_id)

    async def put_settings(self, app_id: str, settings: AppSettings) -> AppSettings:
        saved = await self.settings.put(app_id, settings)
        await self.session.commit()
        return saved

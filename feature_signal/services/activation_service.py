"""C4 - approve: turn a proposal into real changes in Adapty and log every step.

Order (docs/team/C-adapty-proposals.md, chapter 4):
1. write the attributes for every user with values (membership sync; the proposal already counts as executing);
2. create the segment `[fs] <segment_key>` = `p_segment IN [...]` AND the proposal's `adapty_filters`
   (an existing segment with that title is updated, never duplicated);
3. read the trigger placement; its default audience's flow is the control arm;
4. create the A/B test (control `holdout_pct` %, offer the rest) for that segment and start it.
A new draft flow (`needs_publish`) stops after step 2 as `awaiting_publish`; when a human has published the flow,
approving again continues with steps 3 and 4. This service never publishes a flow, in either mode.
Starting a test cannot be undone, so it is only reached through an approve (human or autopilot).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.errors import ApiError
from feature_signal.db.tables import ProposalRow
from feature_signal.domain.models import Condition
from feature_signal.domain.ports import MembershipSync
from feature_signal.integrations.adapty.cli import AdaptyCommands, condition_to_filter, custom_attribute_filter
from feature_signal.schemas.proposals import ProposalOut
from feature_signal.services.membership_service import canonical_segment_keys
from feature_signal.services.proposal_service import ProposalService, check_transition, to_out


def segment_title(segment_key: str) -> str:
    return f"[fs] {segment_key}"


def _step(name: str, ok: bool, **detail: Any) -> dict[str, Any]:
    return {"step": name, "ok": ok, "detail": detail}


def _default_flow_id(placement: dict[str, Any]) -> str:
    defaults = [a for a in placement.get("audiences") or [] if not a.get("segment_ids")]
    default = defaults[-1] if defaults else None
    if not default or default.get("content_type") != "flow" or not default.get("flow_id"):
        raise ApiError(
            409,
            "placement_default_not_a_flow",
            "The placement's default audience is not a plain flow, so there is no control arm to compare with",
        )
    return default["flow_id"]


class ActivationService:
    def __init__(self, session: AsyncSession, commands: AdaptyCommands, membership: MembershipSync) -> None:
        self._session = session
        self._commands = commands
        self._membership = membership
        self._proposals = ProposalService(session)

    async def approve(self, proposal_id: str, decided_by: str = "human") -> ProposalOut:
        row = await self._proposals._get(proposal_id)
        if row.status == "awaiting_publish":
            return await self._resume(row, decided_by)
        check_transition(row.status, "approved")
        row.status, row.decided_by = "approved", decided_by
        row.mode_at_decision = (await self._proposals.get_settings(row.app_id)).mode
        await self._session.commit()
        check_transition(row.status, "executing")
        row.status = "executing"
        await self._session.commit()
        return await self._run(row, decided_by, resumed=False)

    async def _resume(self, row: ProposalRow, decided_by: str) -> ProposalOut:
        flow = await self._commands.flows_get(row.action["flow_id"])
        if flow.get("status") != "published":
            raise ApiError(
                409,
                "flow_not_published",
                "The flow is still a draft. Publish it in Adapty first (a human click), then approve again",
                {"flow_id": row.action["flow_id"], "status": flow.get("status")},
            )
        return await self._run(row, decided_by, resumed=True)

    async def _run(self, row: ProposalRow, decided_by: str, *, resumed: bool) -> ProposalOut:
        steps: list[dict[str, Any]] = []
        current = "write_attributes"
        refs: dict[str, Any] = dict(row.adapty or {})
        try:
            if not resumed:
                synced = await self._membership.sync_users(row.app_id, None)
                refs["attributes_written"] = synced.attributes_written
                steps.append(
                    _step(
                        "write_attributes", True, profiles=synced.changed, attributes_written=synced.attributes_written
                    )
                )

                current = "segments_create"
                segment_id, reused = await self._ensure_segment(row)
                refs["segment_id"] = segment_id
                steps.append(_step("segments_create", True, segment_id=segment_id, reused=reused))

                if row.action.get("needs_publish"):
                    steps.append(_step("awaiting_publish", True, flow_id=row.action["flow_id"]))
                    await self._finish(row, "awaiting_publish", refs, steps, decided_by)
                    return to_out(row)

            current = "placement_read"
            placement = await self._commands.placement_by_developer_id(row.trigger_placement)
            refs["placement_id"] = placement["id"]
            control = _default_flow_id(placement)
            steps.append(_step("placement_read", True, placement_id=placement["id"], control_flow_id=control))
            if control == row.action["flow_id"]:
                raise ApiError(409, "offer_equals_control", "The offered flow is already the placement's default flow")

            current = "ab_tests_create"
            holdout = row.holdout_pct
            created = await self._commands.ab_tests_create(
                f"{segment_title(row.segment_key)} {row.proposal_id}",
                placement_id=placement["id"],
                segment_id=refs["segment_id"],
                arms=[(control, holdout, "control"), (row.action["flow_id"], 100 - holdout, "offer")],
            )
            test_id = created.get("ab_test_id") or created.get("id")
            if not test_id:
                raise ApiError(502, "adapty_cli_bad_output", "Adapty did not return the A/B test id")
            refs["ab_test_id"] = test_id
            steps.append(_step("ab_tests_create", True, ab_test_id=test_id))

            current = "ab_tests_start"
            await self._commands.ab_tests_start(test_id, placement_id=placement["id"], segment_id=refs["segment_id"])
            steps.append(_step("ab_tests_start", True, ab_test_id=test_id))
            await self._finish(row, "live", refs, steps, decided_by)
        except ApiError as exc:
            steps.append(_step(current, False, code=exc.code, message=exc.message))
            await self._finish(row, "failed", refs, steps, decided_by)
        except Exception as exc:  # noqa: BLE001 - never leave a proposal stuck in "executing"
            steps.append(_step(current, False, code="unexpected_error", message=type(exc).__name__))
            await self._finish(row, "failed", refs, steps, decided_by)
        return to_out(row)

    async def _ensure_segment(self, row: ProposalRow) -> tuple[str, bool]:
        values = row.condition.get("value")
        values = [str(v) for v in (values if isinstance(values, list | tuple) else [values])]
        if values == [row.segment_key]:  # not edited by a human: proposals with the same behaviour share one key
            canonical = canonical_segment_keys(await self._proposals.list(row.app_id))
            values = [canonical.get(row.segment_key, row.segment_key)]
        # Freeze the key: the membership sync must keep writing exactly what this segment filters on.
        row.condition = {**row.condition, "value": values}
        filters = [custom_attribute_filter(row.condition.get("attribute", "p_segment"), values)]
        filters += [condition_to_filter(Condition(**f)) for f in row.adapty_filters or []]
        title = segment_title(row.segment_key)
        existing = await self._commands.find_segment_by_title(title)
        if existing:
            await self._commands.segments_update(existing["id"], title, filters)
            return existing["id"], True
        created = await self._commands.segments_create(title, filters)
        if not created.get("id"):
            raise ApiError(502, "adapty_cli_bad_output", "Adapty did not return the segment id")
        return created["id"], False

    async def _finish(
        self, row: ProposalRow, status: str, refs: dict[str, Any], steps: list[dict[str, Any]], decided_by: str
    ) -> None:
        from datetime import datetime, timezone

        check_transition(row.status, status)
        row.status, row.adapty = status, dict(refs)
        row.updated_at = datetime.now(timezone.utc)
        action = "autopilot_start" if decided_by == "autopilot" else "approve"
        await self._proposals.decisions.add(row.app_id, row.proposal_id, decided_by, action, steps)
        await self._session.commit()

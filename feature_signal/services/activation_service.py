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

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update
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
        if row.status == "failed":
            for existing in await self._proposals.list(row.app_id):
                if (
                    existing.proposal_id != row.proposal_id
                    and existing.status in {"live", "executing", "approved"}
                    and existing.trigger_placement == row.trigger_placement
                    and existing.segment_key == row.segment_key
                    and existing.action.flow_id == row.action["flow_id"]
                ):
                    raise ApiError(
                        409,
                        "proposal_already_active",
                        f"This audience and offer are already active in {existing.proposal_id}. "
                        "Open that proposal instead",
                    )
            history = await self._proposals.decisions.list(row.app_id, row.proposal_id)
            if (row.adapty or {}).get("ab_test_id") or any(
                step["step"] in {"ab_tests_create", "ab_tests_start"} for decision in history for step in decision.steps
            ):
                raise ApiError(
                    409,
                    "activation_retry_unsafe",
                    "A/B test creation was already attempted. Check its state in Adapty before retrying",
                )
        mode = (await self._proposals.get_settings(row.app_id)).mode
        await self._claim(row, "approved", decided_by, mode)
        check_transition(row.status, "executing")
        row.status = "executing"
        await self._session.commit()
        return await self._run(row, decided_by, resumed=False)

    async def _claim(self, row: ProposalRow, status: str, decided_by: str, mode: str) -> None:
        claimed = await self._session.execute(
            update(ProposalRow)
            .where(
                ProposalRow.proposal_id == row.proposal_id,
                ProposalRow.status == row.status,
                ProposalRow.updated_at == row.updated_at,
            )
            .values(status=status, decided_by=decided_by, mode_at_decision=mode, updated_at=datetime.now(timezone.utc))
        )
        if claimed.rowcount != 1:
            await self._session.rollback()
            raise ApiError(409, "approval_in_progress", "This proposal is already being approved")
        await self._session.commit()
        await self._session.refresh(row)

    async def _control_flow_id(self, row: ProposalRow, placement: dict[str, Any]) -> str:
        defaults = [a for a in placement.get("audiences") or [] if not a.get("segment_ids")]
        default = defaults[-1] if defaults else {}
        if default.get("content_type") == "flow" and default.get("flow_id"):
            return default["flow_id"]
        if default.get("content_type") != "flow_ab_test" or not default.get("ab_test_id"):
            raise ApiError(
                409,
                "placement_default_not_a_flow",
                "The placement needs a default flow or a flow A/B test to select a control",
            )
        test = await self._commands.ab_tests_get(default["ab_test_id"])
        arms = [arm for arm in test.get("flows", []) if arm.get("flow_id") and arm.get("weight", 0) > 0]
        flow_ids = {arm["flow_id"] for arm in arms}
        offer = row.action["flow_id"]
        # A generated copy is compared with the flow it was copied from.
        base = (row.evidence or {}).get("ai_copy", {}).get("base_flow_id")
        if not base and row.action.get("needs_publish"):
            base = next(
                (
                    edit.get("from")
                    for edit in reversed(row.edits or [])
                    if edit.get("field") == "flow_id" and edit.get("to") == offer
                ),
                None,
            )
        if base in flow_ids and base != offer:
            return base
        controls = {arm["flow_id"] for arm in arms if str(arm.get("title", "")).strip().lower() == "control"}
        if len(controls) == 1:
            return next(iter(controls))
        alternatives = flow_ids - {offer}
        if not controls and offer in flow_ids and len(alternatives) == 1:
            return next(iter(alternatives))
        raise ApiError(
            409,
            "placement_control_ambiguous",
            "The default A/B test has no unambiguous control for this offer. Label one active arm 'control' in Adapty",
        )

    async def _resume(self, row: ProposalRow, decided_by: str) -> ProposalOut:
        flow = await self._commands.flows_get(row.action["flow_id"])
        if flow.get("status") != "published":
            raise ApiError(
                409,
                "flow_not_published",
                "The flow is still a draft. Publish it in Adapty first (a human click), then approve again",
                {"flow_id": row.action["flow_id"], "status": flow.get("status")},
            )
        check_transition(row.status, "executing")
        await self._claim(row, "executing", decided_by, row.mode_at_decision)
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
            control = await self._control_flow_id(row, placement)
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
        check_transition(row.status, status)
        row.status, row.adapty = status, dict(refs)
        row.updated_at = datetime.now(timezone.utc)
        action = "autopilot_start" if decided_by == "autopilot" else "approve"
        await self._proposals.decisions.add(row.app_id, row.proposal_id, decided_by, action, steps)
        await self._session.commit()

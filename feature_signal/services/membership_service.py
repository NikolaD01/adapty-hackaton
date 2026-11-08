"""C9 - membership sync, the fast loop: keep Adapty's attributes in step with a user's values.

For each user we compute what Adapty should hold:
- `f_<feature>_tier` = low / mid / high for every feature whose tier passed measurement (at most 10);
- `p_segment` = `segment_key` of the first live (or executing) proposal whose segment conditions the user meets.
Then we write only what differs from what we last wrote (`null` deletes a key the user no longer has).

Segment conditions of a proposal are read from `evidence["segment_conditions"]`, a list of
`{field, op, value}` over our own values (a rule key, compared as a number) or a tier attribute
(`f_<feature>_tier`, compared as text). Conditions on fields Adapty already knows live in
`adapty_filters` and are applied by Adapty's own segment, not here. No conditions = matches nobody.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any, Protocol

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import FeatureTier, SyncResult
from feature_signal.domain.ports import AttributeWriter, TierStore, ValueStore

MAX_TIER_FEATURES = 10
SEGMENT_ATTRIBUTE = "p_segment"
# Activation (C4) writes the attributes before it marks a proposal live, so those states count too.
COUNTING_STATUSES = frozenset({"live", "executing", "awaiting_publish"})
Attributes = dict[str, str | float | None]


class AttributeState(Protocol):
    """What we last wrote per user, so the next sync PATCHes only the difference."""

    async def get_many(self, app_id: str, customer_user_ids: Sequence[str]) -> dict[str, dict[str, Any]]: ...
    async def put(self, app_id: str, customer_user_id: str, attributes: dict[str, Any]) -> None: ...


class ProposalReader(Protocol):
    async def list(self, app_id: str, status: str | None = None) -> Sequence[Any]: ...


def _is_number(x: Any) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def _holds(actual: Any, op: str, expected: Any) -> bool:
    if op in (">", ">=", "<", "<="):
        if not (_is_number(actual) and _is_number(expected)):
            return False
        return {">": actual > expected, ">=": actual >= expected, "<": actual < expected, "<=": actual <= expected}[op]
    wanted = list(expected) if isinstance(expected, list | tuple) else [expected]
    if op in ("=", "=="):
        return actual in wanted
    if op == "!=":
        return actual not in wanted
    if op == "IN":
        return actual in wanted
    if op == "NOT IN":
        return actual not in wanted
    return False


def _behaviour_signature(proposal: Any) -> str | None:
    conditions = (proposal.evidence or {}).get("segment_conditions") or []
    if not conditions:
        return None
    parts = [{k: c.get(k) for k in ("field", "op", "value")} for c in conditions]
    return json.dumps(
        sorted(parts, key=lambda c: json.dumps(c, sort_keys=True, default=str)), sort_keys=True, default=str
    )


ACTIVATED_STATUSES = ("approved", "executing", "awaiting_publish", "live")


def _frozen_value(proposal: Any) -> str | None:
    """The `p_segment` value an activated proposal's Adapty segment filters on (its `condition.value`)."""
    if proposal.status not in ACTIVATED_STATUSES:
        return None
    condition = getattr(proposal, "condition", None)
    value = condition.get("value") if isinstance(condition, dict) else getattr(condition, "value", None)
    if not (isinstance(value, list | tuple) and len(value) == 1):
        return None
    frozen = str(value[0])
    # approved/executing come before activation stores the key: their own key is not decided yet
    if frozen == proposal.segment_key and proposal.status not in ("live", "awaiting_publish"):
        return None
    return frozen


def canonical_segment_keys(proposals: Sequence[Any]) -> dict[str, str]:
    """Proposals whose behaviour rule is identical share ONE `p_segment` value: the key of the earliest of them.

    A user has a single `p_segment`, and B splits one behaviour group by native filters (platform, country) that Adapty
    applies itself. Without sharing, only the first of those segments would ever get members. Drafts count (so
    activating a later one never re-keys users); rejected and failed proposals do not.

    An activated proposal's key is frozen: activation stores the value its Adapty segment filters on in
    `condition.value`, and that value wins for its behaviour. Otherwise rejecting an earlier draft would re-key the
    users and leave the live Adapty segment (`p_segment IN [old key]`) empty; a human-edited value would also differ.
    """
    first: dict[str, str] = {}
    keys: dict[str, str] = {}
    for proposal in proposals:
        frozen = _frozen_value(proposal)
        if frozen is None:
            continue
        keys[proposal.segment_key] = frozen
        signature = _behaviour_signature(proposal)
        if signature is not None:
            first.setdefault(signature, frozen)
    for proposal in proposals:
        if proposal.status in ("rejected", "failed") or proposal.segment_key in keys:
            continue
        signature = _behaviour_signature(proposal)
        keys.setdefault(
            proposal.segment_key,
            proposal.segment_key if signature is None else first.setdefault(signature, proposal.segment_key),
        )
    return keys


def segment_matches(conditions: Sequence[dict[str, Any]], values: dict[str, float], tiers: dict[str, str]) -> bool:
    """True when every condition holds. A missing field or an empty list never matches."""
    if not conditions:
        return False
    for condition in conditions:
        field = condition.get("field")
        if field in values:
            actual: Any = values[field]
        elif field in tiers:
            actual = tiers[field]
        else:
            return False
        if not _holds(actual, str(condition.get("op", "")).upper(), condition.get("value")):
            return False
    return True


class MembershipService:
    """Implements the `MembershipSync` port."""

    def __init__(
        self,
        values: ValueStore,
        tiers: TierStore,
        proposals: ProposalReader,
        state: AttributeState,
        writer: AttributeWriter,
        *,
        concurrency: int = 8,
    ) -> None:
        self._values = values
        self._tiers = tiers
        self._proposals = proposals
        self._state = state
        self._writer = writer
        self._concurrency = max(1, concurrency)

    async def sync_users(self, app_id: str, customer_user_ids: Sequence[str] | None) -> SyncResult:
        matrix = await self._values.matrix(app_id)
        by_user = {
            u: dict(zip(matrix.columns, row, strict=True)) for u, row in zip(matrix.users, matrix.values, strict=True)
        }
        ids = list(dict.fromkeys(by_user if customer_user_ids is None else customer_user_ids))
        passed = sorted((t for t in await self._tiers.list(app_id) if t.passed), key=lambda t: t.feature)[
            :MAX_TIER_FEATURES
        ]
        everything = list(await self._proposals.list(app_id))
        live = [p for p in everything if p.status in COUNTING_STATUSES]
        canonical = canonical_segment_keys(everything)
        last = await self._state.get_many(app_id, ids)

        semaphore = asyncio.Semaphore(self._concurrency)

        async def one(user: str) -> tuple[str, Attributes, int]:
            desired = self._desired(by_user.get(user, {}), passed, live, canonical)
            previous = last.get(user, {})
            changes: Attributes = {k: v for k, v in desired.items() if previous.get(k) != v}
            changes.update({k: None for k in previous if k not in desired})
            if changes:
                async with semaphore:
                    await self._writer.write(user, changes)
            return user, desired, len(changes)

        outcomes = await asyncio.gather(*(one(u) for u in ids), return_exceptions=True)
        changed = written = failed = 0
        causes: dict[str, int] = {}
        first_message = ""
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                failed += 1
                code = outcome.code if isinstance(outcome, ApiError) else "unexpected_error"
                causes[code] = causes.get(code, 0) + 1
                if not first_message and isinstance(outcome, ApiError):
                    first_message = outcome.message
                continue
            user, desired, count = outcome
            if count:
                await self._state.put(app_id, user, desired)
                changed += 1
                written += count
        if failed:
            raise ApiError(
                502,
                "membership_sync_partial",
                f"{failed} of {len(ids)} users could not be written to Adapty. {changed} users updated."
                + (f" {first_message}" if first_message else ""),
                {"failed": failed, "checked": len(ids), "changed": changed, "causes": causes},
            )
        return SyncResult(checked=len(ids), changed=changed, attributes_written=written)

    @staticmethod
    def _desired(
        values: dict[str, float], passed: Sequence[FeatureTier], live: Sequence[Any], canonical: dict[str, str]
    ) -> Attributes:
        desired: Attributes = {}
        tier_by_attribute: dict[str, str] = {}
        for tier in passed:
            if tier.rule_key in values:
                label = tier.tier(values[tier.rule_key])
                tier_by_attribute[tier.attribute] = label
                desired[tier.attribute] = label
        for proposal in live:
            conditions = (proposal.evidence or {}).get("segment_conditions") or []
            if segment_matches(conditions, values, tier_by_attribute):
                desired[SEGMENT_ATTRIBUTE] = canonical.get(proposal.segment_key, proposal.segment_key)
                break
        return desired


class SqlMembershipSync:
    """`MembershipSync` port for A's ingest: opens its own session per call and commits the written state.

    Wiring is `app.state.membership_sync = SqlMembershipSync(SessionFactory, writer)` in `create_app()`
    (shared file `main.py`, goes through contract-change).
    """

    def __init__(self, session_factory: Any, writer: AttributeWriter, *, concurrency: int = 8) -> None:
        self._session_factory = session_factory
        self._writer = writer
        self._concurrency = concurrency

    async def sync_users(self, app_id: str, customer_user_ids: Sequence[str] | None) -> SyncResult:
        async with self._session_factory() as session:
            service = build_membership_service(session, self._writer, concurrency=self._concurrency)
            try:
                return await service.sync_users(app_id, customer_user_ids)
            finally:
                await session.commit()  # keep the state of the users that were written, even if others failed


def build_membership_service(session: Any, writer: AttributeWriter, *, concurrency: int = 8) -> MembershipService:
    from feature_signal.repositories.proposals import AttributeStateRepository
    from feature_signal.repositories.tiers import TierRepository
    from feature_signal.repositories.values import ValueRepository
    from feature_signal.services.proposal_service import ProposalService

    return MembershipService(
        ValueRepository(session),
        TierRepository(session),
        ProposalService(session),
        AttributeStateRepository(session),
        writer,
        concurrency=concurrency,
    )

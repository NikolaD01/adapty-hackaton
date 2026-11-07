"""C9 - membership sync, the fast loop: keep Adapty's attributes in step with a user's values.

For each user we compute what Adapty should hold:
- `f_<feature>_tier` = low / mid / high for every feature whose tier passed measurement (at most 10);
- `p_segment` = `segment_key` of the first live proposal whose segment conditions the user meets.
Then we write only what differs from what we last wrote (`null` deletes a key the user no longer has).

Segment conditions of a proposal are read from `evidence["segment_conditions"]`, a list of
`{field, op, value}` over our own values (a rule key, compared as a number) or a tier attribute
(`f_<feature>_tier`, compared as text). Conditions on fields Adapty already knows live in
`adapty_filters` and are applied by Adapty's own segment, not here. No conditions = matches nobody.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Protocol

from feature_signal.core.errors import ApiError
from feature_signal.domain.models import FeatureTier, SyncResult
from feature_signal.domain.ports import AttributeWriter, TierStore, ValueStore

MAX_TIER_FEATURES = 10
SEGMENT_ATTRIBUTE = "p_segment"
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
    if op == "IN":
        return actual in wanted
    if op == "NOT IN":
        return actual not in wanted
    return False


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
        live = list(await self._proposals.list(app_id, "live"))
        last = await self._state.get_many(app_id, ids)

        semaphore = asyncio.Semaphore(self._concurrency)

        async def one(user: str) -> tuple[str, Attributes, int]:
            desired = self._desired(by_user.get(user, {}), passed, live)
            previous = last.get(user, {})
            changes: Attributes = {k: v for k, v in desired.items() if previous.get(k) != v}
            changes.update({k: None for k in previous if k not in desired})
            if changes:
                async with semaphore:
                    await self._writer.write(user, changes)
            return user, desired, len(changes)

        outcomes = await asyncio.gather(*(one(u) for u in ids), return_exceptions=True)
        changed = written = failed = 0
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                failed += 1
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
                f"{failed} of {len(ids)} users could not be written to Adapty; the rest were",
                {"failed": failed, "checked": len(ids), "changed": changed},
            )
        return SyncResult(checked=len(ids), changed=changed, attributes_written=written)

    @staticmethod
    def _desired(values: dict[str, float], passed: Sequence[FeatureTier], live: Sequence[Any]) -> Attributes:
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
                desired[SEGMENT_ATTRIBUTE] = proposal.segment_key
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

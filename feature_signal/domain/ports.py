"""Ports: the interfaces services depend on (docs/contracts/ports.md). Shared file: contract-change."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from feature_signal.domain.models import (
    BatchResult,
    Event,
    EventType,
    Explanation,
    FeatureMatrix,
    ProposalDraft,
    Ranking,
    Rule,
    ServedFlow,
)


class EventTypeRepo(Protocol):  # A
    async def upsert(self, app_id: str, key: str, name: str, description: str, family: str | None) -> EventType: ...
    async def list(self, app_id: str) -> list[EventType]: ...


class EventSink(Protocol):  # A — idempotent on event_id
    async def record_batch(self, app_id: str, events: Sequence[Event]) -> BatchResult: ...


class EventReader(Protocol):  # A
    async def history(self, app_id: str, customer_user_id: str, since: datetime | None) -> list[Event]: ...
    async def users(self, app_id: str) -> list[str]: ...


class RuleRepo(Protocol):  # A
    async def save(self, app_id: str, rule: Rule) -> Rule: ...
    async def list(self, app_id: str) -> list[Rule]: ...


class ValueStore(Protocol):  # A — read by B and C
    async def put_many(self, app_id: str, rule_key: str, values: dict[str, float]) -> None: ...
    async def matrix(self, app_id: str) -> FeatureMatrix: ...


class LLMProvider(Protocol):  # B — used by B (rules, explain) and C (paywall copy)
    async def suggest_rules(self, catalog: list[EventType]) -> list[tuple[Rule, str]]: ...
    async def explain(self, ranking: Ranking, catalog: list[EventType]) -> Explanation: ...
    async def paywall_copy(self, segment_label: str, base_config: dict[str, Any]) -> dict[str, Any]: ...


class ProposalSink(Protocol):  # C — B hands drafts to C
    async def create_many(self, app_id: str, drafts: Sequence[ProposalDraft]) -> list[str]: ...


class AttributeWriter(Protocol):  # C
    async def write(self, customer_user_id: str, attributes: dict[str, str | float | None]) -> None: ...


class AdaptyCli(Protocol):  # C
    async def run(self, *args: str) -> dict[str, Any]: ...


class FlowLookup(Protocol):  # C
    async def served(self, customer_user_id: str, placement: str) -> ServedFlow: ...

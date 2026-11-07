"""In-memory fakes of the ports (docs/contracts/ports.md). Any area may use them in tests.
Adding a fake for a new port is a contract change."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from feature_signal.domain.models import (
    EventType,
    Explanation,
    FeatureMatrix,
    ProposalDraft,
    Ranking,
    Rule,
    ServedFlow,
)


class FakeValueStore:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))

    async def put_many(self, app_id: str, rule_key: str, values: dict[str, float]) -> None:
        for cuid, v in values.items():
            self.data[app_id][cuid][rule_key] = v

    async def matrix(self, app_id: str) -> FeatureMatrix:
        users = sorted(self.data[app_id])
        columns = sorted({k for row in self.data[app_id].values() for k in row})
        values = [[self.data[app_id][u].get(c, 0.0) for c in columns] for u in users]
        return FeatureMatrix(users=users, columns=columns, values=values)


class FakeProposalSink:
    def __init__(self) -> None:
        self.created: list[ProposalDraft] = []

    async def create_many(self, app_id: str, drafts: Sequence[ProposalDraft]) -> list[str]:
        self.created.extend(drafts)
        return [f"pr_{i:02d}" for i in range(len(self.created) - len(drafts) + 1, len(self.created) + 1)]


class FakeAttributeWriter:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict[str, Any]]] = []

    async def write(self, customer_user_id: str, attributes: dict[str, str | float | None]) -> None:
        self.writes.append((customer_user_id, dict(attributes)))


class FakeAdaptyCli:
    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.responses = responses or {}

    async def run(self, *args: str) -> dict[str, Any]:
        self.calls.append(args)
        return self.responses.get(" ".join(args[:2]), {})


class FakeLLM:
    def __init__(self, suggestions: list[tuple[Rule, str]] | None = None) -> None:
        self.suggestions = suggestions or []

    async def suggest_rules(self, catalog: list[EventType]) -> list[tuple[Rule, str]]:
        return self.suggestions

    async def explain(self, ranking: Ranking, catalog: list[EventType]) -> Explanation:
        return Explanation(summary=f"{ranking.feature} separates users", hypothesis="", confidence=0.5)

    async def paywall_copy(self, segment_label: str, base_config: dict[str, Any]) -> dict[str, Any]:
        return {**base_config, "title": f"For {segment_label}"}


class FakeFlowLookup:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    async def served(self, customer_user_id: str, placement: str) -> ServedFlow:
        flow = self.mapping.get(customer_user_id)
        return ServedFlow(customer_user_id, segment_hash="fake", flow_id=flow, flow_name=flow)

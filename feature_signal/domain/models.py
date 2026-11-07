"""Domain models (pure data, no I/O). Field names follow docs/contracts/api.md. Shared file: contract-change."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Measure = Literal["count", "distinct", "exists", "days_active", "ratio", "sum", "last", "max", "min"]
Tier = Literal["low", "mid", "high"]
Direction = Literal["up", "down"]
ProposalStatus = Literal["draft", "approved", "executing", "awaiting_publish", "live", "failed", "rejected"]
Actor = Literal["human", "autopilot"]


@dataclass(frozen=True)
class Feature:
    """A group of events the developer defines; its width (how many events) is the developer's choice."""

    key: str
    name: str
    description: str
    plans: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EventType:
    action_id: int
    key: str
    name: str
    description: str
    features: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Event:
    event_id: str
    customer_user_id: str
    key: str
    occurred_at: datetime
    received_at: datetime | None = None
    props: dict[str, Any] = field(default_factory=dict)
    decision_id: str | None = None


@dataclass(frozen=True)
class BatchResult:
    accepted: int
    duplicates: int
    unknown_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Where:
    prop: str
    op: Literal["eq", "lt", "lte", "gt", "gte"]
    value: float | str | bool


@dataclass(frozen=True)
class RuleDefinition:
    event_keys: list[str]
    measure: Measure
    window_days: int | None = None
    distinct_prop: str | None = None
    value_prop: str | None = None
    denominator_event_keys: list[str] | None = None
    where: Where | None = None


@dataclass(frozen=True)
class Rule:
    key: str
    name: str
    description: str
    definition: RuleDefinition
    source: Literal["human", "ai", "default"] = "human"
    feature: str | None = None
    rule_id: int | None = None


@dataclass(frozen=True)
class FeatureMatrix:
    """One row per customer_user_id, one column per rule key (A produces it, B and C read it)."""

    users: list[str]
    columns: list[str]
    values: list[list[float]]


@dataclass(frozen=True)
class Ranking:
    feature: str
    threshold: float
    direction: Direction
    lift: float
    ci_low: float
    ci_high: float
    holdout_lift: float
    n_above: int
    n_below: int
    passed: bool


@dataclass(frozen=True)
class FeatureTier:
    """Measured cut points (B) that turn one feature value into f_<feature>_tier (written by C)."""

    feature: str
    rule_key: str
    low_max: float
    mid_max: float
    passed: bool

    @property
    def attribute(self) -> str:
        return f"f_{self.feature}_tier"

    def tier(self, value: float) -> Tier:
        return "low" if value <= self.low_max else "mid" if value <= self.mid_max else "high"


@dataclass(frozen=True)
class SyncResult:
    checked: int
    changed: int
    attributes_written: int


@dataclass(frozen=True)
class Condition:
    field: str
    op: str
    value: Any


@dataclass(frozen=True)
class SegmentCandidate:
    segment_key: str
    label: str
    conditions: list[Condition]
    size: int
    net_arpu_90d: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class Uplift:
    segment_key: str
    test: str
    better_arm: str
    worse_arm: str
    diff_net_90d: float
    ci_low: float
    ci_high: float
    n_a: int
    n_b: int


@dataclass(frozen=True)
class ProposalDraft:
    segment_key: str
    trigger_placement: str
    condition: Condition
    flow_id: str
    flow_name: str
    expected_diff: float
    ci_low: float
    ci_high: float
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    holdout_pct: int = 20
    cooldown_days: int = 7
    adapty_filters: list[Condition] = field(default_factory=list)
    highlight_feature: str | None = None
    needs_publish: bool = False


@dataclass(frozen=True)
class Explanation:
    summary: str
    hypothesis: str
    confidence: float


@dataclass(frozen=True)
class ServedFlow:
    customer_user_id: str
    segment_hash: str
    flow_id: str | None
    flow_name: str | None

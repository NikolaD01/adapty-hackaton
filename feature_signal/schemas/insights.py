"""Insight schemas (owner B). Mirrors docs/contracts/api.md."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class InsightRunIn(BaseModel):
    source: Literal["offline", "live"] = "offline"


class RankingOut(BaseModel):
    feature: str
    threshold: float
    direction: Literal["up", "down"]
    lift: float
    ci_low: float
    ci_high: float
    holdout_lift: float
    n_above: int
    n_below: int
    passed: bool


class ConditionOut(BaseModel):
    field: str
    op: str
    value: Any


class SegmentOut(BaseModel):
    segment_key: str
    label: str
    conditions: list[ConditionOut]
    size: int
    net_arpu_90d: float
    ci_low: float
    ci_high: float


class UpliftOut(BaseModel):
    segment_key: str
    test: str
    better_arm: str
    worse_arm: str
    diff_net_90d: float
    ci_low: float
    ci_high: float
    n_a: int
    n_b: int


class InsightRunOut(BaseModel):
    run_id: str
    source: Literal["offline", "live"]
    created_at: datetime
    rankings: list[RankingOut]
    segments: list[SegmentOut]
    uplift: list[UpliftOut]

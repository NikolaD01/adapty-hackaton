"""Proposals, settings, decisions, lookup, paywall draft (owner C). Mirrors docs/contracts/api.md."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ProposalStatus = Literal["draft", "approved", "executing", "live", "failed", "rejected"]
Actor = Literal["human", "autopilot"]


class ProposalCondition(BaseModel):
    attribute: str
    op: Literal["IN", "NOT IN", ">", ">=", "<", "<="]
    value: Any


class ProposalAction(BaseModel):
    type: Literal["flow"] = "flow"
    flow_id: str
    flow_name: str | None = None


class ExpectedEffect(BaseModel):
    metric: Literal["net_revenue_90d"] = "net_revenue_90d"
    diff: float
    ci_low: float
    ci_high: float


class ProposalEdit(BaseModel):
    at: datetime
    field: str
    from_: Any = Field(alias="from")
    to: Any

    model_config = {"populate_by_name": True}


class AdaptyRefs(BaseModel):
    segment_id: str | None = None
    placement_id: str | None = None
    ab_test_id: str | None = None
    attributes_written: int = 0


class ProposalIn(BaseModel):
    trigger_placement: str
    segment_key: str
    condition: ProposalCondition
    action: ProposalAction
    holdout_pct: int = Field(default=20, ge=0, le=50)
    cooldown_days: int = Field(default=7, ge=0, le=90)
    expected_effect: ExpectedEffect
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_by: Literal["ai", "human"] = "ai"


class ProposalsIn(BaseModel):
    proposals: list[ProposalIn] = Field(min_length=1)


class ProposalOut(ProposalIn):
    proposal_id: str
    app_id: str
    status: ProposalStatus
    decided_by: Actor | None = None
    mode_at_decision: Literal["human", "autopilot"] | None = None
    edits: list[ProposalEdit] = Field(default_factory=list)
    adapty: AdaptyRefs = Field(default_factory=AdaptyRefs)
    created_at: datetime
    updated_at: datetime


class ProposalPatch(BaseModel):
    """Only these fields may change (never paywall JSON)."""

    model_config = {"extra": "forbid"}

    holdout_pct: int | None = Field(default=None, ge=0, le=50)
    cooldown_days: int | None = Field(default=None, ge=0, le=90)
    flow_id: str | None = None
    condition_value: Any | None = None
    trigger_placement: str | None = None


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class AutopilotLimits(BaseModel):
    max_live_proposals: int = Field(default=3, ge=0, le=20)
    min_holdout_pct: int = Field(default=10, ge=0, le=50)
    allow_publish_flow: Literal[False] = False


class AppSettings(BaseModel):
    mode: Literal["human", "autopilot"] = "human"
    autopilot: AutopilotLimits = Field(default_factory=AutopilotLimits)


class DecisionStep(BaseModel):
    step: str
    ok: bool
    detail: dict[str, Any] = Field(default_factory=dict)


class DecisionOut(BaseModel):
    decision_id: str
    proposal_id: str
    decided_by: Actor
    action: Literal["approve", "reject", "autopilot_start"]
    steps: list[DecisionStep]
    at: datetime


class LookupIn(BaseModel):
    placement: str
    customer_user_ids: list[str] = Field(min_length=1, max_length=10)


class LookupResult(BaseModel):
    customer_user_id: str
    segment_hash: str
    flow_id: str | None
    flow_name: str | None


class LookupOut(BaseModel):
    results: list[LookupResult]


class PaywallDraftIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    product_ids: list[str] = Field(default_factory=list)


class PaywallDraftOut(BaseModel):
    base_flow_id: str
    draft_flow_id: str
    status: Literal["draft"]
    changed_paths: list[str]

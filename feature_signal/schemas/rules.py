"""Rules & values schemas (owner A; suggestions owner B). Mirrors docs/contracts/api.md."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Measure = Literal["count", "distinct", "exists", "days_active", "ratio", "sum", "last", "max", "min"]
VALUE_MEASURES = {"sum", "last", "max", "min"}


class WhereIn(BaseModel):
    """Keep only events whose prop matches, e.g. tokens_left <= 0."""

    prop: str
    op: Literal["eq", "lt", "lte", "gt", "gte"]
    value: float | str | bool


class RuleDefinitionIn(BaseModel):
    event_keys: list[str] = Field(min_length=1)
    measure: Measure
    distinct_prop: str | None = None
    value_prop: str | None = None  # sum/last/max/min read this numeric prop
    denominator_event_keys: list[str] | None = None  # ratio = count(event_keys) / count(denominator)
    where: WhereIn | None = None
    window_days: int | None = Field(default=None, ge=1, le=90)

    @model_validator(mode="after")
    def measure_has_its_inputs(self) -> "RuleDefinitionIn":
        if self.measure == "distinct" and not self.distinct_prop:
            raise ValueError("measure 'distinct' needs distinct_prop")
        if self.measure in VALUE_MEASURES and not self.value_prop:
            raise ValueError(f"measure '{self.measure}' needs value_prop")
        if self.measure == "ratio" and not self.denominator_event_keys:
            raise ValueError("measure 'ratio' needs denominator_event_keys")
        return self


class RuleIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")  # stays with us; default rules can be long
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    source: Literal["human", "ai", "default"] = "human"  # default = created with the feature
    feature: str | None = None  # groups the value into the feature profile
    definition: RuleDefinitionIn
    value_type: Literal["float"] = "float"


class RuleOut(RuleIn):
    rule_id: int
    created_at: datetime


class RuleSuggestion(BaseModel):
    rule: RuleIn
    rationale: str


class RuleSuggestionsOut(BaseModel):
    suggestions: list[RuleSuggestion]
    model: str


class ValueItem(BaseModel):
    customer_user_id: str
    rule_key: str
    value: float
    computed_at: datetime


class ValuesPage(BaseModel):
    items: list[ValueItem]
    next_cursor: str | None = None


class RecomputeOut(BaseModel):
    users: int
    rules: int

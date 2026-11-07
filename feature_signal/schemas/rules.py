"""Rules & values schemas (owner A; suggestions owner B). Mirrors docs/contracts/api.md."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RuleDefinitionIn(BaseModel):
    event_keys: list[str] = Field(min_length=1)
    measure: Literal["count", "distinct", "exists", "days_active"]
    distinct_prop: str | None = None
    window_days: int | None = Field(default=None, ge=1, le=90)

    @model_validator(mode="after")
    def distinct_needs_prop(self) -> "RuleDefinitionIn":
        if self.measure == "distinct" and not self.distinct_prop:
            raise ValueError("measure 'distinct' needs distinct_prop")
        return self


class RuleIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    source: Literal["human", "ai"] = "human"
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

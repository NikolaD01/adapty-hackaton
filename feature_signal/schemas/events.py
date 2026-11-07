"""Ingest & catalog schemas (owner A). Mirrors docs/contracts/api.md. Shared file: contract-change."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Feature keys become Adapty attribute keys `f_<feature>_tier` (Adapty key limit: 30 chars) → max 22 chars.
FEATURE_KEY = r"^[a-z][a-z0-9_]{1,21}$"
MAX_PROPS = 20
MAX_PROP_STRING = 100  # short labels and ids only; free text (e.g. a prompt) is never sent


class FeatureIn(BaseModel):
    key: str = Field(pattern=FEATURE_KEY)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    plans: list[str] = Field(default_factory=list, description="Access levels / products that include it")


class FeatureOut(FeatureIn):
    created_at: datetime


class EventTypeIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    features: list[str] = Field(default_factory=list, max_length=5)


class EventTypeOut(EventTypeIn):
    action_id: int
    created_at: datetime


class EventIn(BaseModel):
    event_id: UUID
    customer_user_id: str = Field(min_length=1, max_length=128)
    key: str
    occurred_at: datetime
    props: dict[str, bool | int | float | str | None] = Field(default_factory=dict)
    decision_id: str | None = None

    @field_validator("props")
    @classmethod
    def props_are_small_values(cls, props: dict[str, Any]) -> dict[str, Any]:
        if len(props) > MAX_PROPS:
            raise ValueError(f"at most {MAX_PROPS} props per event")
        for name, value in props.items():
            if isinstance(value, str) and len(value) > MAX_PROP_STRING:
                raise ValueError(f"prop '{name}' is longer than {MAX_PROP_STRING} chars; send a number or label")
        return props


class EventBatchIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=500)


class EventBatchOut(BaseModel):
    accepted: int
    duplicates: int
    unknown_keys: list[str] = Field(default_factory=list)


class TimelineItem(BaseModel):
    event_id: UUID
    key: str
    occurred_at: datetime
    received_at: datetime
    props: dict[str, Any] = Field(default_factory=dict)


class TimelineOut(BaseModel):
    customer_user_id: str
    items: list[TimelineItem]


class FeatureProfileItem(BaseModel):
    feature: str
    name: str
    values: dict[str, float]  # rule_key -> value, rules of this feature only
    tier: Literal["low", "mid", "high"] | None = None  # set only for measured features
    computed_at: datetime | None = None


class FeatureProfileOut(BaseModel):
    customer_user_id: str
    features: list[FeatureProfileItem]

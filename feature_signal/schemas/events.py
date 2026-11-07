"""Ingest & catalog schemas (owner A). Mirrors docs/contracts/api.md. Shared file: contract-change."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventTypeIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    family: str | None = Field(default=None, max_length=40)


class EventTypeOut(EventTypeIn):
    action_id: int
    created_at: datetime


class EventIn(BaseModel):
    event_id: UUID
    customer_user_id: str = Field(min_length=1, max_length=128)
    key: str
    occurred_at: datetime
    props: dict[str, Any] = Field(default_factory=dict)
    decision_id: str | None = None


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

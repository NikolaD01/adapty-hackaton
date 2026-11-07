"""SQLAlchemy tables. Owner A: every table, including C's proposals/decisions (docs/team/A-ingest-rules.md).

Column names follow docs/contracts/api.md. Nested contract parts are JSON columns. Changing a column =
new Alembic migration in feature_signal/db/migrations/versions (never edit an applied one).
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

APP_ID = String(64)
USER_ID = String(128)
KEY = String(40)
RULE_KEY = String(80)  # <feature>_used_<event> can reach 68 chars; rule keys never go to Adapty


class Base(DeclarativeBase):
    pass


# ---------- catalog -------------------------------------------------------------------------------


class FeatureRow(Base):
    __tablename__ = "features"

    app_id: Mapped[str] = mapped_column(APP_ID, primary_key=True)
    key: Mapped[str] = mapped_column(String(22), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    plans: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventTypeRow(Base):
    __tablename__ = "event_types"
    __table_args__ = (UniqueConstraint("app_id", "key", name="uq_event_types_app_key"),)

    action_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(APP_ID)
    key: Mapped[str] = mapped_column(KEY)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventTypeFeatureRow(Base):
    """An event may belong to several features; it is counted in each."""

    __tablename__ = "event_type_features"

    action_id: Mapped[int] = mapped_column(ForeignKey("event_types.action_id"), primary_key=True)
    feature_key: Mapped[str] = mapped_column(String(22), primary_key=True)
    app_id: Mapped[str] = mapped_column(APP_ID)


# ---------- history -------------------------------------------------------------------------------


class EventRow(Base):
    """Append-only. Windows use occurred_at (phone clock); received_at is for lag debugging only."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_app_user_time", "app_id", "customer_user_id", "occurred_at"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    app_id: Mapped[str] = mapped_column(APP_ID)
    customer_user_id: Mapped[str] = mapped_column(USER_ID)
    action_id: Mapped[int] = mapped_column(ForeignKey("event_types.action_id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    props: Mapped[dict] = mapped_column(JSON, default=dict)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class UserActionCountRow(Base):
    """Running counters, changed only inside the ingest transaction for rows actually inserted."""

    __tablename__ = "user_action_counts"

    app_id: Mapped[str] = mapped_column(APP_ID, primary_key=True)
    customer_user_id: Mapped[str] = mapped_column(USER_ID, primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("event_types.action_id"), primary_key=True)
    n: Mapped[int] = mapped_column(Integer, default=0)
    last_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ---------- rules and values ----------------------------------------------------------------------


class RuleRow(Base):
    __tablename__ = "rules"
    __table_args__ = (UniqueConstraint("app_id", "key", name="uq_rules_app_key"),)

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(APP_ID)
    key: Mapped[str] = mapped_column(RULE_KEY)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(10))  # human | ai | default
    feature: Mapped[str | None] = mapped_column(String(22), nullable=True)
    definition: Mapped[dict] = mapped_column(JSON)
    value_type: Mapped[str] = mapped_column(String(10), default="float")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserValueRow(Base):
    __tablename__ = "user_values"

    app_id: Mapped[str] = mapped_column(APP_ID, primary_key=True)
    customer_user_id: Mapped[str] = mapped_column(USER_ID, primary_key=True)
    rule_key: Mapped[str] = mapped_column(RULE_KEY, primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FeatureTierRow(Base):
    """Written by B after an insight run (TierStore), read by C's membership sync."""

    __tablename__ = "feature_tiers"

    app_id: Mapped[str] = mapped_column(APP_ID, primary_key=True)
    feature: Mapped[str] = mapped_column(String(22), primary_key=True)
    rule_key: Mapped[str] = mapped_column(RULE_KEY)
    low_max: Mapped[float] = mapped_column(Float)
    mid_max: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ---------- C: proposals, decisions, settings, attribute state ------------------------------------


class ProposalRow(Base):
    __tablename__ = "proposals"
    __table_args__ = (Index("ix_proposals_app_status", "app_id", "status"),)

    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    app_id: Mapped[str] = mapped_column(APP_ID)
    status: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[str] = mapped_column(String(10))
    decided_by: Mapped[str | None] = mapped_column(String(10), nullable=True)
    mode_at_decision: Mapped[str | None] = mapped_column(String(10), nullable=True)
    trigger_placement: Mapped[str] = mapped_column(String(100))
    segment_key: Mapped[str] = mapped_column(String(50))
    condition: Mapped[dict] = mapped_column(JSON)
    adapty_filters: Mapped[list] = mapped_column(JSON, default=list)
    action: Mapped[dict] = mapped_column(JSON)
    holdout_pct: Mapped[int] = mapped_column(Integer)
    cooldown_days: Mapped[int] = mapped_column(Integer)
    expected_effect: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    edits: Mapped[list] = mapped_column(JSON, default=list)
    adapty: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DecisionRow(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    app_id: Mapped[str] = mapped_column(APP_ID)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.proposal_id"))
    decided_by: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(20))
    steps: Mapped[list] = mapped_column(JSON, default=list)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AppSettingsRow(Base):
    __tablename__ = "app_settings"

    app_id: Mapped[str] = mapped_column(APP_ID, primary_key=True)
    settings: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdaptyAttributeStateRow(Base):
    """Last attributes C wrote per user, so the membership sync PATCHes only what changed."""

    __tablename__ = "adapty_attribute_state"

    app_id: Mapped[str] = mapped_column(APP_ID, primary_key=True)
    customer_user_id: Mapped[str] = mapped_column(USER_ID, primary_key=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

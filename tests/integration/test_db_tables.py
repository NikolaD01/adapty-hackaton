"""A1: the first migration creates every table, matches the models, and each table round-trips a row."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from feature_signal.db import tables as t
from feature_signal.db.session import enable_sqlite_pragmas

ROOT = Path(__file__).resolve().parents[2]
APP = "c6c7bdd1-1010-4343-8b29-837a77793cab"
NOW = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_url(tmp_path) -> str:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    command.check(cfg)  # raises if the models and the migrations disagree
    return url


@pytest.fixture
def session(db_url):
    engine = create_engine(db_url)
    enable_sqlite_pragmas(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def test_upgrade_creates_every_table(db_url):
    names = set(inspect(create_engine(db_url)).get_table_names())
    assert set(t.Base.metadata.tables) <= names


def test_sqlite_runs_in_wal_with_foreign_keys(session):
    assert session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_one_row_per_table_round_trips(session):
    et = t.EventTypeRow(app_id=APP, key="regenerate_click", name="Regenerate", description="d", created_at=NOW)
    session.add_all(
        [t.FeatureRow(app_id=APP, key="ai_generate", name="AI", description="d", plans=["premium"], created_at=NOW), et]
    )
    session.flush()
    session.add_all(
        [
            t.EventTypeFeatureRow(action_id=et.action_id, feature_key="ai_generate", app_id=APP),
            t.EventRow(
                event_id="0b6f0c1e-5d1a-4c7e-9a0e-3f0f2b7c9a11",
                app_id=APP,
                customer_user_id="u_42",
                action_id=et.action_id,
                occurred_at=NOW,
                received_at=NOW,
                props={"tokens_left": 0},
            ),
            t.UserActionCountRow(app_id=APP, customer_user_id="u_42", action_id=et.action_id, n=1, last_ts=NOW),
            t.RuleRow(
                app_id=APP,
                key="ai_generate_uses_7d",
                name="n",
                description="d",
                source="default",
                feature="ai_generate",
                definition={"event_keys": ["regenerate_click"], "measure": "count"},
                created_at=NOW,
            ),
            t.UserValueRow(
                app_id=APP, customer_user_id="u_42", rule_key="ai_generate_uses_7d", value=9.0, computed_at=NOW
            ),
            t.FeatureTierRow(
                app_id=APP,
                feature="ai_generate",
                rule_key="ai_generate_uses_7d",
                low_max=2,
                mid_max=7,
                passed=True,
                updated_at=NOW,
            ),
            t.ProposalRow(
                proposal_id="pr_01",
                app_id=APP,
                status="draft",
                created_by="ai",
                trigger_placement="main",
                segment_key="ai_power_free",
                condition={"attribute": "p_segment", "op": "IN", "value": ["ai_power_free"]},
                action={"type": "flow", "flow_id": "f"},
                holdout_pct=20,
                cooldown_days=7,
                expected_effect={"diff": 1.0},
                reason="r",
                created_at=NOW,
                updated_at=NOW,
            ),
            t.AppSettingsRow(app_id=APP, settings={"mode": "human"}, updated_at=NOW),
            t.AdaptyAttributeStateRow(
                app_id=APP, customer_user_id="u_42", attributes={"p_segment": "ai_power_free"}, updated_at=NOW
            ),
        ]
    )
    session.flush()
    session.add(
        t.DecisionRow(
            decision_id="dc_01",
            app_id=APP,
            proposal_id="pr_01",
            decided_by="human",
            action="approve",
            steps=[{"step": "segments_create", "ok": True}],
            at=NOW,
        )
    )
    session.commit()

    assert session.scalar(select(t.EventRow.props)) == {"tokens_left": 0}
    assert session.scalar(select(t.FeatureRow.plans)) == ["premium"]
    assert session.scalar(select(t.EventTypeFeatureRow.feature_key)) == "ai_generate"
    assert session.scalar(select(t.UserActionCountRow.n)) == 1
    assert session.scalar(select(t.RuleRow.definition))["measure"] == "count"
    assert session.scalar(select(t.UserValueRow.value)) == 9.0
    assert session.scalar(select(t.FeatureTierRow.passed)) is True
    assert session.scalar(select(t.ProposalRow.status)) == "draft"
    assert session.scalar(select(t.DecisionRow.steps))[0]["ok"] is True
    assert session.scalar(select(t.AppSettingsRow.settings)) == {"mode": "human"}
    assert session.scalar(select(t.AdaptyAttributeStateRow.attributes)) == {"p_segment": "ai_power_free"}


def test_duplicate_event_id_is_refused_by_the_primary_key(session):
    et = t.EventTypeRow(app_id=APP, key="generate_click", name="n", description="d", created_at=NOW)
    session.add(et)
    session.flush()
    row = dict(
        event_id="e1",
        app_id=APP,
        customer_user_id="u",
        action_id=et.action_id,
        occurred_at=NOW,
        received_at=NOW,
        props={},
    )
    session.add(t.EventRow(**row))
    session.flush()
    session.add(t.EventRow(**row))
    with pytest.raises(IntegrityError):
        session.flush()


def test_event_type_key_is_unique_per_app(session):
    session.add(t.EventTypeRow(app_id=APP, key="k", name="n", description="d", created_at=NOW))
    session.flush()
    session.add(t.EventTypeRow(app_id=APP, key="k", name="n2", description="d", created_at=NOW))
    with pytest.raises(IntegrityError):
        session.flush()

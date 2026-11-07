"""The examples in docs/contracts/api.md must validate against the pydantic schemas."""

import pytest
from pydantic import ValidationError

from feature_signal.schemas.events import EventBatchIn, EventTypeIn
from feature_signal.schemas.proposals import AppSettings, ProposalPatch
from feature_signal.schemas.rules import RuleIn


def test_event_batch_example_validates():
    batch = EventBatchIn.model_validate(
        {
            "events": [
                {
                    "event_id": "0b6f0c1e-5d1a-4c7e-9a0e-3f0f2b7c9a11",
                    "customer_user_id": "lumen_282506_00007",
                    "key": "bg_remove",
                    "occurred_at": "2026-11-07T17:59:58Z",
                    "props": {"photo_id": "p_123"},
                }
            ]
        }
    )
    assert batch.events[0].key == "bg_remove"


def test_event_type_key_pattern_rejects_spaces():
    with pytest.raises(ValidationError):
        EventTypeIn(key="bg remove", name="x", description="y")


def test_distinct_rule_requires_prop():
    with pytest.raises(ValidationError):
        RuleIn.model_validate(
            {
                "key": "photos_7d",
                "name": "n",
                "description": "d",
                "definition": {"event_keys": ["bg_remove"], "measure": "distinct"},
            }
        )


def test_patch_rejects_paywall_json():
    with pytest.raises(ValidationError):
        ProposalPatch.model_validate({"paywall_config": {"title": "x"}})


def test_settings_default_is_human_and_never_publishes():
    s = AppSettings()
    assert s.mode == "human"
    assert s.autopilot.allow_publish_flow is False

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


def test_feature_key_fits_adapty_attribute_key():
    from feature_signal.schemas.events import FeatureIn

    FeatureIn(key="ai_generate", name="AI generation", description="d")
    assert len("f_" + "a" * 22 + "_tier") <= 30
    with pytest.raises(ValidationError):
        FeatureIn(key="a" * 23, name="n", description="d")


def test_event_type_belongs_to_features():
    et = EventTypeIn(key="regenerate_click", name="n", description="d", features=["ai_generate"])
    assert et.features == ["ai_generate"]


def test_event_props_carry_numbers_but_not_free_text():
    base = {
        "event_id": "0b6f0c1e-5d1a-4c7e-9a0e-3f0f2b7c9a11",
        "customer_user_id": "u_42",
        "key": "generate_click",
        "occurred_at": "2026-11-07T18:02:00Z",
    }
    ok = EventBatchIn.model_validate({"events": [{**base, "props": {"tokens_used": 40, "tokens_left": 0}}]})
    assert ok.events[0].props["tokens_left"] == 0
    with pytest.raises(ValidationError):
        EventBatchIn.model_validate({"events": [{**base, "props": {"prompt": "x" * 101}}]})


@pytest.mark.parametrize(
    "definition",
    [
        {"event_keys": ["generate_click"], "measure": "sum"},
        {"event_keys": ["regenerate_click"], "measure": "ratio"},
    ],
)
def test_value_and_ratio_measures_need_their_inputs(definition):
    with pytest.raises(ValidationError):
        RuleIn.model_validate({"key": "r", "name": "n", "description": "d", "definition": definition})


def test_tokens_exhausted_rule_validates():
    rule = RuleIn.model_validate(
        {
            "key": "tokens_exhausted_7d",
            "name": "Ran out of tokens in the last 7 days",
            "description": "At least one AI event reported tokens_left <= 0",
            "feature": "ai_generate",
            "definition": {
                "event_keys": ["generate_click", "regenerate_click"],
                "measure": "exists",
                "where": {"prop": "tokens_left", "op": "lte", "value": 0},
                "window_days": 7,
            },
        }
    )
    assert rule.definition.where.op == "lte"


def test_feature_tier_cut_points():
    from feature_signal.domain.models import FeatureTier

    t = FeatureTier(feature="ai_generate", rule_key="ai_generate_uses_7d", low_max=2, mid_max=7, passed=True)
    assert t.attribute == "f_ai_generate_tier"
    assert [t.tier(v) for v in (0, 2, 3, 7, 8)] == ["low", "low", "mid", "mid", "high"]

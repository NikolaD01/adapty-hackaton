"""Segments retain raw, reproducible predicates and measured cohort statistics."""

import pandas as pd
import pytest

from feature_signal.domain.models import Condition, FeatureTier
from feature_signal.domain.ranking import build_segments, segment_key, segment_mask


def fixture_frame():
    return pd.DataFrame(
        {
            "user_id": [f"u{i:03d}" for i in range(120)],
            "edits": [float(i // 30) for i in range(120)],
            "net_revenue_90d": [float((i // 30 + 1) * 2) for i in range(120)],
        }
    )


def test_key_ignores_condition_and_in_value_order():
    left = [Condition("edits", ">", 2), Condition("platform", "IN", ["iOS", "Android"])]
    right = [Condition("platform", "IN", ["Android", "iOS"]), Condition("edits", ">", 2)]
    assert segment_key(left) == segment_key(right)
    assert len(segment_key(left)) <= 50
    assert segment_key(left) != segment_key([Condition("edits", ">", 3), right[0]])


def test_segments_use_raw_rule_bounds_and_exact_cohort_revenue():
    frame = fixture_frame()
    segments = build_segments(frame, [FeatureTier("editor", "edits", 1.0, 2.0, True)])
    assert len(segments) == 3
    cohorts = {
        tuple(frame.loc[segment_mask(frame, segment.conditions), "edits"].unique()): segment for segment in segments
    }
    assert cohorts[(0.0, 1.0)].size == 60
    assert cohorts[(0.0, 1.0)].net_arpu_90d == 3.0
    assert cohorts[(2.0,)].size == 30
    assert cohorts[(2.0,)].net_arpu_90d == 6.0
    assert cohorts[(3.0,)].size == 30
    assert cohorts[(3.0,)].net_arpu_90d == 8.0
    for segment in segments:
        assert segment.ci_low <= segment.net_arpu_90d <= segment.ci_high
        assert all(condition.field == "edits" for condition in segment.conditions)
    assert cohorts[(3.0,)].ci_low == cohorts[(3.0,)].ci_high == 8.0


def test_available_baseline_fields_are_preserved_and_future_fields_are_not_invented():
    frame = fixture_frame().assign(platform="iOS", subscription_state="free", country_tier="tier_1")
    segments = build_segments(frame, [FeatureTier("editor", "edits", 1.0, 2.0, True)])
    assert len(segments) == 3
    for segment in segments:
        filters = {condition.field: condition.value for condition in segment.conditions if condition.field != "edits"}
        assert filters == {"platform": "iOS", "subscription_state": "free", "country_tier": "tier_1"}
    absent = build_segments(fixture_frame(), [FeatureTier("editor", "edits", 1.0, 2.0, True)])
    assert all(condition.field == "edits" for segment in absent for condition in segment.conditions)


def test_cap_and_row_order_do_not_change_candidates_or_intervals():
    frame = fixture_frame().assign(platform=["iOS", "Android", "other"] * 40)
    tiers = [FeatureTier("editor", "edits", 1.0, 2.0, True)]
    segments = build_segments(frame, tiers)
    assert len(segments) == 5
    assert segments == build_segments(frame.sample(frac=1, random_state=7), tiers)
    assert segments == build_segments(frame, tiers)
    assert all(segment.size > 0 for segment in segments)


def test_empty_unpassed_missing_rule_and_null_metadata_are_safe():
    frame = fixture_frame()
    tier = FeatureTier("editor", "edits", 1.0, 2.0, True)
    assert build_segments(frame.iloc[:0], [tier]) == []
    assert build_segments(frame, []) == []
    assert build_segments(frame, [FeatureTier("editor", "edits", 1, 2, False)]) == []
    assert build_segments(frame, [FeatureTier("editor", "missing", 1, 2, True)]) == []
    assert build_segments(frame.assign(platform=None), [tier]) == build_segments(frame, [tier])


@pytest.mark.parametrize(
    "op,value,expected",
    [
        (">", 1, [False, False, True, False]),
        (">=", 1, [False, True, True, False]),
        ("<", 1, [True, False, False, False]),
        ("<=", 1, [True, True, False, False]),
        ("==", 1, [False, True, False, False]),
        ("=", 1, [False, True, False, False]),
        ("!=", 1, [True, False, True, False]),
        ("IN", [0, 2], [True, False, True, False]),
        ("NOT IN", [0, 2], [False, True, False, False]),
        ("IS NULL", None, [False, False, False, True]),
        ("IS NOT NULL", None, [True, True, True, False]),
    ],
)
def test_segment_mask_known_operators_and_nulls(op, value, expected):
    frame = pd.DataFrame({"value": [0.0, 1.0, 2.0, None]})
    assert segment_mask(frame, [Condition("value", op, value)]).tolist() == expected


def test_missing_field_fails_closed_and_multiple_predicates_are_conjoined():
    frame = pd.DataFrame({"value": [0, 1, 2, 3]})
    assert not segment_mask(frame, [Condition("missing", "!=", 1)]).any()
    assert segment_mask(frame, [Condition("value", ">", 0), Condition("value", "<=", 2)]).tolist() == [
        False,
        True,
        True,
        False,
    ]
    with pytest.raises(ValueError, match="operator"):
        segment_mask(frame, [Condition("value", "contains", 2)])


@pytest.mark.parametrize("mutation", ["duplicate", "nonfinite", "negative"])
def test_segment_measurements_reject_invalid_cohort(mutation):
    frame = fixture_frame()
    if mutation == "duplicate":
        frame.loc[1, "user_id"] = frame.loc[0, "user_id"]
    else:
        frame.loc[0, "net_revenue_90d"] = float("inf") if mutation == "nonfinite" else -1
    with pytest.raises(ValueError):
        build_segments(frame, [FeatureTier("editor", "edits", 1, 2, True)])

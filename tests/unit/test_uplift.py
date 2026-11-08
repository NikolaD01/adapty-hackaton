from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from feature_signal.domain.models import Condition, SegmentCandidate
from feature_signal.domain.uplift import by_segment, compare_arms, refund_diagnostics

TEST = "Main: 3 plans vs lifetime anchor (NA)"


def cohort():
    return pd.DataFrame(
        {
            "user_id": [f"u{i:03d}" for i in range(200)],
            "ab_test": [TEST] * 200,
            "flow": ["main"] * 100 + ["main_lifetime"] * 100,
            "placement": ["main"] * 200,
            "edits": [5] * 200,
            "net_revenue_90d": [2.0] * 100 + [5.0] * 100,
            "paid_transactions_90d": [2] * 200,
            "refunded_transactions_90d": [0] * 100 + [1] * 100,
        }
    )


def segment():
    return SegmentCandidate("power", "Power", [Condition("edits", ">", 4)], 200, 3.5, 3, 4)


def test_uplift_sign_and_size():
    assert compare_arms([2.0] * 100, [5.0] * 100) == pytest.approx((3, 3, 3))
    assert compare_arms([5.0] * 100, [2.0] * 100) == pytest.approx((-3, -3, -3))
    assert compare_arms([2.0] * 100, [2.0] * 100) == pytest.approx((0, 0, 0))


def test_interval_contains_known_difference_and_is_reproducible():
    rng = np.random.default_rng(7)
    control = rng.normal(20, 2, 1000)
    treatment = rng.normal(23, 2, 1000)
    result = compare_arms(control, treatment)
    assert result[1] < 3 < result[2]
    assert result == compare_arms(control, treatment)


@pytest.mark.parametrize("bad", [[], [float("nan")], [float("inf")], [-1]])
def test_invalid_arm_is_rejected(bad):
    with pytest.raises(ValueError):
        compare_arms(bad, [1, 2])


def test_segment_uplift_preserves_winner_orientation_and_counts():
    frame = cohort().iloc[:180]
    result = by_segment(frame, [segment()])[0]
    assert (result.better_arm, result.worse_arm) == ("main_lifetime", "main")
    assert (result.n_a, result.n_b) == (80, 100)
    assert (result.diff_net_90d, result.ci_low, result.ci_high) == (3, 3, 3)
    frame = frame.copy()
    frame["net_revenue_90d"] = 10 - frame.net_revenue_90d
    result = by_segment(frame, [segment()])[0]
    assert (result.better_arm, result.worse_arm) == ("main", "main_lifetime")
    assert (result.n_a, result.n_b) == (100, 80)
    assert (result.diff_net_90d, result.ci_low, result.ci_high) == (3, 3, 3)


def test_nonrandom_placement_and_unknown_experiments_are_not_compared():
    frame = cohort()
    frame["ab_test"] = None
    assert by_segment(frame, [segment()]) == []
    frame["ab_test"] = "not a documented randomized experiment"
    assert by_segment(frame, [segment()]) == []


def test_missing_arm_or_empty_segment_yields_no_comparison():
    assert by_segment(cohort().iloc[:100], [segment()]) == []
    empty = replace(segment(), conditions=[Condition("edits", ">", 10)])
    assert by_segment(cohort(), [empty]) == []


def test_unknown_arm_does_not_pollute_documented_experiment():
    frame = cohort()
    extra = frame.iloc[:10].copy()
    extra["user_id"] = [f"other{i}" for i in range(10)]
    extra["flow"] = "unrelated"
    extra["net_revenue_90d"] = 10000
    assert by_segment(pd.concat([frame, extra]), [segment()]) == by_segment(frame, [segment()])


def test_duplicate_user_is_rejected_and_reordering_is_stable():
    frame = cohort()
    with pytest.raises(ValueError, match="unique"):
        by_segment(pd.concat([frame, frame.iloc[:1]]), [segment()])
    assert by_segment(frame.sample(frac=1, random_state=2), [segment()]) == by_segment(frame, [segment()])


def test_refunds_report_paid_transaction_denominator_for_each_arm():
    result = refund_diagnostics(cohort(), segment(), TEST)
    assert result["main_lifetime"] == {
        "users": 100,
        "paid_transactions": 200,
        "refunded_transactions": 100,
        "refund_rate": 0.5,
        "denominator": "paid_transactions_90d",
    }
    assert result["main"]["refund_rate"] == 0


def test_equal_arms_are_not_a_positive_recommendation():
    frame = cohort()
    frame["net_revenue_90d"] = 2.0
    result = by_segment(frame, [segment()])[0]
    assert result.ci_low <= 0 <= result.ci_high

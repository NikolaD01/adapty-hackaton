"""Randomized offer comparisons. Behavioral rankings never select an offer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_signal.domain.models import SegmentCandidate, Uplift
from feature_signal.domain.ranking import segment_mask

# The dataset's documented random assignments, not placement-selected populations.
RANDOMIZED_TESTS = {
    "Main: 3 plans vs lifetime anchor (NA)": ("main", "main", "main_lifetime"),
    "Onboarding: annual trial vs weekly first": ("onboarding", "onb_trial", "onb_weekly"),
    "Settings: upgrade vs lifetime anchor": ("settings", "settings", "main_lifetime"),
}


def compare_arms(control, treatment, *, seed: int = 42, resamples: int = 400) -> tuple[float, float, float]:
    """Treatment minus control mean net revenue and user-bootstrap 90% interval."""
    arms = [np.asarray(values, dtype=float) for values in (control, treatment)]
    if resamples < 2 or any(
        values.ndim != 1 or not len(values) or not np.isfinite(values).all() or (values < 0).any() for values in arms
    ):
        raise ValueError("Arms must contain finite, nonnegative outcomes and at least one user")
    rng = np.random.default_rng(seed)
    left, right = arms
    samples = [
        rng.choice(right, len(right), replace=True).mean() - rng.choice(left, len(left), replace=True).mean()
        for _ in range(resamples)
    ]
    low, high = np.quantile(samples, [0.05, 0.95])
    return float(right.mean() - left.mean()), float(low), float(high)


def _validate(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"user_id", "net_revenue_90d", "ab_test", "flow"}
    if not required <= set(frame.columns):
        raise ValueError(f"Uplift frame is missing columns: {sorted(required - set(frame.columns))}")
    if frame.user_id.isna().any() or frame.user_id.duplicated().any():
        raise ValueError("Uplift requires unique, nonmissing user IDs")
    outcomes = pd.to_numeric(frame.net_revenue_90d, errors="raise")
    if not np.isfinite(outcomes).all() or (outcomes < 0).any():
        raise ValueError("Uplift requires finite nonnegative outcomes")
    return frame.sort_values("user_id")


def by_segment(frame: pd.DataFrame, segments: list[SegmentCandidate]) -> list[Uplift]:
    """Report comparisons; only a positive lower bound supports recommending the better arm.

    n_a always counts better_arm users; n_b counts worse_arm users. Intervals are
    reoriented with the winning sample mean. Intervals crossing zero remain descriptive.
    """
    frame = _validate(frame)
    results = []
    for segment in sorted(segments, key=lambda value: value.segment_key):
        selected = frame.loc[segment_mask(frame, segment.conditions)]
        for test, (_, control_name, treatment_name) in RANDOMIZED_TESTS.items():
            experiment = selected.loc[selected.ab_test == test]
            control = experiment.loc[experiment.flow == control_name, "net_revenue_90d"]
            treatment = experiment.loc[experiment.flow == treatment_name, "net_revenue_90d"]
            if control.empty or treatment.empty:
                continue
            diff, low, high = compare_arms(control, treatment)
            better, worse, n_a, n_b = treatment_name, control_name, len(treatment), len(control)
            if diff < 0:
                better, worse, n_a, n_b = control_name, treatment_name, len(control), len(treatment)
                diff, low, high = -diff, -high, -low
            results.append(Uplift(segment.segment_key, test, better, worse, diff, low, high, n_a, n_b))
    return results


def refund_diagnostics(frame: pd.DataFrame, segment: SegmentCandidate, test: str) -> dict[str, dict]:
    """Refunded paid transactions / paid transactions; an empty denominator yields None."""
    frame = _validate(frame)
    if test not in RANDOMIZED_TESTS:
        return {}
    required = {"paid_transactions_90d", "refunded_transactions_90d"}
    if not required <= set(frame.columns):
        raise ValueError("Refund diagnostics require paid and refunded transaction counts")
    selected = frame.loc[segment_mask(frame, segment.conditions) & (frame.ab_test == test)]
    result = {}
    for arm in RANDOMIZED_TESTS[test][1:]:
        members = selected.loc[selected.flow == arm]
        paid = int(members.paid_transactions_90d.sum())
        refunded = int(members.refunded_transactions_90d.sum())
        result[arm] = {
            "users": len(members),
            "paid_transactions": paid,
            "refunded_transactions": refunded,
            "refund_rate": refunded / paid if paid else None,
            "denominator": "paid_transactions_90d",
        }
    return result

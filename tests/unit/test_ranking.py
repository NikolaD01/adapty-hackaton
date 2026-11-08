"""Measured rankings must generalize and never turn invalid ratios into evidence."""

import math

import numpy as np
import pytest

from feature_signal.domain.models import FeatureMatrix
from feature_signal.domain.ranking import hypotheses, rank


def binary_fixture(*, down=False):
    users = [f"u{i:04d}" for i in range(2000)]
    matrix = FeatureMatrix(users, ["edits"], [[float(i >= 1000)] for i in range(2000)])
    outcome = {user: (2.0 if (i >= 1000) == down else 10.0) for i, user in enumerate(users)}
    return matrix, outcome


@pytest.mark.parametrize("down,lift,direction", [(False, 5.0, "up"), (True, 0.2, "down")])
def test_hand_calculated_lift_and_interval(down, lift, direction):
    matrix, outcome = binary_fixture(down=down)
    result = rank(matrix, outcome)[0]
    assert result.threshold == 0.0
    assert result.lift == pytest.approx(lift)
    assert result.holdout_lift == pytest.approx(lift)
    assert result.direction == direction
    assert result.ci_low == pytest.approx(lift)
    assert result.ci_high == pytest.approx(lift)
    assert result.n_above + result.n_below == 1400
    assert min(result.n_above, result.n_below) >= 150
    assert result.passed


def test_holdout_changes_do_not_change_training_threshold_or_interval():
    matrix, outcome = binary_fixture()
    before = rank(matrix, outcome)[0]
    held_out = np.random.default_rng(42).permutation(2000)[1400:]
    changed = dict(outcome)
    for index in held_out:
        changed[matrix.users[index]] = 100.0 if index < 1000 else 1.0
    after = rank(matrix, changed)[0]
    assert after.threshold == before.threshold
    assert (after.lift, after.ci_low, after.ci_high) == (before.lift, before.ci_low, before.ci_high)
    assert after.holdout_lift == pytest.approx(0.01)
    assert not after.passed


def test_outcome_alignment_and_order_do_not_change_result():
    matrix, outcome = binary_fixture()
    reordered = FeatureMatrix(matrix.users[::-1], matrix.columns, matrix.values[::-1])
    assert rank(matrix, outcome) == rank(reordered, dict(reversed(list(outcome.items()))))


def test_fixed_independent_noise_does_not_pass():
    rng = np.random.default_rng(102)
    users = [f"u{i:04d}" for i in range(4000)]
    matrix = FeatureMatrix(users, ["noise"], [[float(v)] for v in rng.integers(0, 2, len(users))])
    outcomes = {user: (10.0 if i >= 2000 else 2.0) for i, user in enumerate(users)}
    result = rank(matrix, outcomes)[0]
    assert not result.passed
    assert result.direction == "down"
    assert result.holdout_lift > 1


@pytest.mark.parametrize(
    "values,outcome",
    [
        ([[1.0]] * 2000, 5.0),
        ([[float(i >= 1000)] for i in range(2000)], 0.0),
        ([[float(i >= 1990)] for i in range(2000)], 5.0),
    ],
)
def test_constant_zero_revenue_and_small_groups_fail_finitely(values, outcome):
    users = [f"u{i:04d}" for i in range(2000)]
    result = rank(FeatureMatrix(users, ["value"], values), dict.fromkeys(users, outcome))[0]
    assert not result.passed
    assert all(
        math.isfinite(value)
        for value in (result.threshold, result.lift, result.holdout_lift, result.ci_low, result.ci_high)
    )


def test_undersized_ranking_reports_actual_training_counts_at_emitted_threshold():
    users = [f"u{i:03d}" for i in range(200)]
    matrix = FeatureMatrix(users, ["value"], [[float(i >= 100)] for i in range(200)])
    result = rank(matrix, dict.fromkeys(users, 1.0))[0]
    assert result.threshold == 0.0
    assert result.n_above == 72
    assert result.n_below == 68
    assert not result.passed


def test_nonfinite_values_and_outcomes_are_excluded_and_hypotheses_are_unranked():
    matrix, outcome = binary_fixture()
    values = [[row[0], float("nan"), float("inf")] for row in matrix.values]
    values.append([float("inf"), 3.0, 4.0])
    extended = FeatureMatrix(matrix.users + ["unknown"], ["edits", "live", "invalid"], values)
    outcome["unknown"] = float("nan")
    assert hypotheses(extended, outcome) == ["live", "invalid"]
    assert [item.feature for item in rank(extended, outcome)] == ["edits"]


def test_holdout_groups_below_minimum_cannot_pass():
    users = [f"u{i:04d}" for i in range(500)]
    matrix = FeatureMatrix(users, ["value"], [[float(i >= 250)] for i in range(500)])
    outcome = {user: (10.0 if i >= 250 else 2.0) for i, user in enumerate(users)}
    result = rank(matrix, outcome)[0]
    assert result.lift == pytest.approx(5.0)
    assert not result.passed


def test_empty_matrix_has_no_rankings_or_hypotheses():
    assert rank(FeatureMatrix([], [], []), {}) == []
    assert hypotheses(FeatureMatrix([], [], []), {}) == []


def test_variable_outcomes_interval_contains_population_ratio():
    matrix, outcome = binary_fixture()
    rng = np.random.default_rng(31)
    outcome = {user: outcome[user] * rng.uniform(0.8, 1.2) for user in matrix.users}
    result = rank(matrix, outcome)[0]
    assert result.ci_low < 5 < result.ci_high
    assert result.passed


def test_negative_outcomes_are_rejected():
    matrix, outcome = binary_fixture()
    outcome[matrix.users[0]] = -1.0
    with pytest.raises(ValueError, match="nonnegative"):
        rank(matrix, outcome)


@pytest.mark.parametrize(
    "matrix",
    [
        FeatureMatrix(["u", "u"], ["rule"], [[1.0], [2.0]]),
        FeatureMatrix(["u"], ["rule"], [[1.0, 2.0]]),
    ],
)
def test_malformed_matrix_is_rejected(matrix):
    with pytest.raises(ValueError):
        rank(matrix, {"u": 1.0})

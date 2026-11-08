"""Pure behavioral evidence: ranking, measured tiers, and segment definitions."""

from __future__ import annotations

import hashlib
import json
import operator
import re
from collections.abc import Mapping
from itertools import combinations

import numpy as np
import pandas as pd

from feature_signal.domain.models import Condition, FeatureMatrix, FeatureTier, Ranking, SegmentCandidate

_SEED = 42
_RESAMPLES = 400
_MIN_GROUP = 150


def _aligned(matrix: FeatureMatrix, outcome: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray]:
    if len(set(matrix.users)) != len(matrix.users) or len(set(matrix.columns)) != len(matrix.columns):
        raise ValueError("Matrix user IDs and column keys must be unique")
    values = np.asarray(matrix.values, dtype=float)
    if not matrix.users and not matrix.values:
        values = np.empty((0, len(matrix.columns)))
    if values.shape != (len(matrix.users), len(matrix.columns)):
        raise ValueError("Matrix shape does not match users and columns")
    if any(np.isfinite(value) and value < 0 for value in outcome.values()):
        raise ValueError("Outcomes must be nonnegative")
    rows = sorted(
        (index for index, user in enumerate(matrix.users) if user in outcome and np.isfinite(outcome[user])),
        key=lambda index: matrix.users[index],
    )
    return values[rows], np.asarray([outcome[matrix.users[index]] for index in rows], dtype=float)


def hypotheses(matrix: FeatureMatrix, outcome: Mapping[str, float]) -> list[str]:
    """Rules with no finite measurement joined to a finite known outcome."""
    values, _ = _aligned(matrix, outcome)
    return [key for index, key in enumerate(matrix.columns) if not np.isfinite(values[:, index]).any()]


def _mean(values: np.ndarray) -> float:
    if not len(values):
        return 0.0
    with np.errstate(over="ignore", invalid="ignore"):
        result = float(np.mean(values))
    # Dividing first avoids overflowing a sum of individually finite revenues.
    return result if np.isfinite(result) else float(np.sum(values / len(values)))


def _ratio(above: np.ndarray, below: np.ndarray) -> float | None:
    if not len(above) or not len(below):
        return None
    numerator, denominator = _mean(above), _mean(below)
    if denominator <= 0 or numerator < 0:
        return None
    ratio = numerator / denominator
    return ratio if np.isfinite(ratio) else None


def _ratio_interval(above: np.ndarray, below: np.ndarray) -> tuple[float, float, bool]:
    rng = np.random.default_rng(_SEED)
    samples = []
    for _ in range(_RESAMPLES):
        ratio = _ratio(rng.choice(above, len(above)), rng.choice(below, len(below)))
        if ratio is None:
            return 1.0, 1.0, False
        samples.append(ratio)
    low, high = np.quantile(samples, [0.05, 0.95])
    return float(low), float(high), True


def _strength(lift: float) -> float:
    return abs(float(np.log(lift))) if lift > 0 else float("inf")


def rank(matrix: FeatureMatrix, outcome: Mapping[str, float]) -> list[Ranking]:
    """Select thresholds on 70% training users; validate unchanged cuts on 30%.

    lift/CI/n_above/n_below describe finite training rows. holdout_lift describes
    finite held-out rows. Ratios always mean (>threshold)/(<=threshold).
    Undefined ratios and undersized groups cannot pass. No joinable values means
    a hypothesis, so no Ranking is emitted for that column.
    """
    values, outcomes = _aligned(matrix, outcome)
    permutation = np.random.default_rng(_SEED).permutation(len(outcomes))
    boundary = int(0.7 * len(outcomes))
    train, holdout = np.sort(permutation[:boundary]), np.sort(permutation[boundary:])
    results = []
    for column, key in enumerate(matrix.columns):
        if not np.isfinite(values[:, column]).any():
            continue
        finite_train = train[np.isfinite(values[train, column])]
        finite_holdout = holdout[np.isfinite(values[holdout, column])]
        x, y = values[finite_train, column], outcomes[finite_train]
        best = None
        for threshold in np.unique(x)[:-1]:
            above, below = y[x > threshold], y[x <= threshold]
            if min(len(above), len(below)) < _MIN_GROUP:
                continue
            lift = _ratio(above, below)
            if lift is not None and (best is None or _strength(lift) > _strength(best[1])):
                best = float(threshold), lift, above, below
        if best is None:
            threshold = float(np.min(x)) if len(x) else 0.0
            n_above = int(np.count_nonzero(x > threshold))
            n_below = int(np.count_nonzero(x <= threshold))
            results.append(Ranking(key, threshold, "up", 1.0, 1.0, 1.0, 1.0, n_above, n_below, False))
            continue
        threshold, lift, above, below = best
        low, high, valid_interval = _ratio_interval(above, below)
        hx, hy = values[finite_holdout, column], outcomes[finite_holdout]
        h_above, h_below = hy[hx > threshold], hy[hx <= threshold]
        holdout_lift = _ratio(h_above, h_below)
        direction = "up" if lift >= 1 else "down"
        passed = (
            valid_interval
            and holdout_lift is not None
            and min(len(h_above), len(h_below)) >= _MIN_GROUP
            and ((low > 1 and holdout_lift > 1) if direction == "up" else (high < 1 and holdout_lift < 1))
        )
        results.append(
            Ranking(
                key,
                threshold,
                direction,
                lift,
                low,
                high,
                holdout_lift if holdout_lift is not None else 1.0,
                len(above),
                len(below),
                bool(passed),
            )
        )
    return results


def _mean_interval(values: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(_SEED)
    samples = [_mean(rng.choice(values, len(values))) for _ in range(_RESAMPLES)]
    low, high = np.quantile(samples, [0.05, 0.95])
    return float(low), float(high)


def derive_tiers(
    matrix: FeatureMatrix,
    outcome: Mapping[str, float],
    rankings: list[Ranking],
    rule_features: Mapping[str, str],
) -> list[FeatureTier]:
    """Choose the strongest passing rule per developer feature, then measure three tiers.

    Candidate cuts are the training ranking cut and aligned-value tertiles.
    Prefer a valid pair containing that cut, then the most balanced cohorts.
    Tiers are descriptive on all aligned users, not a second held-out claim.
    """
    values, outcomes = _aligned(matrix, outcome)
    candidates = sorted(
        (ranking for ranking in rankings if ranking.passed and ranking.feature in rule_features),
        key=lambda ranking: (-_strength(ranking.lift), ranking.feature),
    )
    seen = set()
    tiers = []
    passed_count = 0
    for ranking in candidates:
        feature = rule_features[ranking.feature]
        if feature in seen or ranking.feature not in matrix.columns:
            continue
        seen.add(feature)
        column = values[:, matrix.columns.index(ranking.feature)]
        finite = np.isfinite(column)
        x, y = column[finite], outcomes[finite]
        if not len(x):
            continue
        thirds = np.quantile(x, [1 / 3, 2 / 3])
        cuts = sorted({ranking.threshold, *map(float, thirds)})
        possibilities = []
        for low_max, mid_max in combinations(cuts, 2):
            groups = [y[x <= low_max], y[(x > low_max) & (x <= mid_max)], y[x > mid_max]]
            if not all(len(group) for group in groups):
                continue
            means = [_mean(group) for group in groups]
            if not means[0] < means[1] < means[2]:
                continue
            _, low_upper = _mean_interval(groups[0])
            high_lower, _ = _mean_interval(groups[2])
            if low_upper < high_lower:
                priority = (ranking.threshold not in (low_max, mid_max), -min(map(len, groups)), low_max, mid_max)
                possibilities.append((priority, low_max, mid_max))
        passed = bool(possibilities)
        if passed:
            if passed_count >= 10:
                continue
            _, low_max, mid_max = min(possibilities)
            passed_count += 1
        else:
            low_max, mid_max = cuts[0], cuts[-1]
        tiers.append(FeatureTier(feature, ranking.feature, low_max, mid_max, passed))
    return tiers


_NATIVE_FIELDS = ("platform", "subscription_state", "country_tier")
_COMPARISONS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def _plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _condition_token(condition: Condition) -> str:
    op = condition.op.strip().upper()
    op = "==" if op == "=" else op
    value = _plain(condition.value)
    if op in ("IN", "NOT IN"):
        value = sorted({json.dumps(item, sort_keys=True, allow_nan=False) for item in value})
    return json.dumps([condition.field, op, value], sort_keys=True, allow_nan=False, separators=(",", ":"))


def segment_key(conditions: list[Condition]) -> str:
    """Order-independent, <=50-character slug for raw behavioral and native predicates."""
    tokens = sorted({_condition_token(condition) for condition in conditions})
    digest = hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()[:16]
    fields = "-".join(sorted({condition.field for condition in conditions}))
    prefix = re.sub(r"[^a-z0-9]+", "-", fields.lower()).strip("-") or "all"
    return f"{prefix[:33].rstrip('-')}-{digest}"


def segment_mask(frame: pd.DataFrame, conditions: list[Condition]) -> pd.Series:
    """Conjoin raw predicates; missing fields and null comparisons fail closed."""
    mask = pd.Series(True, index=frame.index, dtype=bool)
    for condition in conditions:
        if condition.field not in frame:
            return pd.Series(False, index=frame.index, dtype=bool)
        values = frame[condition.field]
        op = condition.op.strip().upper()
        if op in _COMPARISONS:
            numbers = pd.to_numeric(values, errors="coerce")
            selected = np.isfinite(numbers) & _COMPARISONS[op](numbers, condition.value)
        elif op in ("=", "==", "!="):
            selected = values.eq(condition.value) if op != "!=" else values.ne(condition.value)
            selected &= values.notna()
        elif op in ("IN", "NOT IN"):
            selected = values.isin(condition.value)
            selected = selected if op == "IN" else ~selected
            selected &= values.notna()
        elif op == "IS NULL":
            selected = values.isna()
        elif op == "IS NOT NULL":
            selected = values.notna()
        else:
            raise ValueError(f"Unsupported condition operator: {condition.op}")
        if op not in ("IS NULL", "IS NOT NULL") and pd.api.types.is_numeric_dtype(values):
            selected &= np.isfinite(values)
        mask &= selected.fillna(False).astype(bool)
    return mask


def build_segments(frame: pd.DataFrame, tiers: list[FeatureTier]) -> list[SegmentCandidate]:
    """Measure up to five largest observed tier/native cohorts; never infer native data.

    All available native fields are combined as observed tuples. Without complete
    native metadata a tier-only candidate is retained. Conditions remain raw rule
    bounds, allowing downstream uplift to evaluate them against the same frame.
    """
    if frame.empty or not any(tier.passed for tier in tiers):
        return []
    required = {"user_id", "net_revenue_90d"}
    if not required <= set(frame.columns):
        raise ValueError("Segments require user_id and net_revenue_90d")
    if frame.user_id.isna().any() or frame.user_id.duplicated().any():
        raise ValueError("Segments require unique, nonmissing user IDs")
    frame = frame.sort_values("user_id").copy()
    outcomes = pd.to_numeric(frame.net_revenue_90d, errors="raise")
    if not np.isfinite(outcomes).all() or (outcomes < 0).any():
        raise ValueError("Segments require finite nonnegative outcomes")
    frame["net_revenue_90d"] = outcomes
    native_fields = [field for field in _NATIVE_FIELDS if field in frame and frame[field].notna().any()]
    definitions = {}
    for tier in sorted(tiers, key=lambda tier: (tier.feature, tier.rule_key)):
        if not tier.passed or tier.rule_key not in frame:
            continue
        if not np.isfinite([tier.low_max, tier.mid_max]).all() or tier.low_max >= tier.mid_max:
            continue
        bounds = [
            ("low", [Condition(tier.rule_key, "<=", tier.low_max)]),
            ("mid", [Condition(tier.rule_key, ">", tier.low_max), Condition(tier.rule_key, "<=", tier.mid_max)]),
            ("high", [Condition(tier.rule_key, ">", tier.mid_max)]),
        ]
        for level, behavior in bounds:
            members = frame.loc[segment_mask(frame, behavior)]
            if members.empty:
                continue
            native_tuples = members[native_fields].dropna().drop_duplicates() if native_fields else pd.DataFrame()
            native_variants = [
                [Condition(field, "==", _plain(row[field])) for field in native_fields]
                for _, row in native_tuples.iterrows()
            ] or [[]]
            for native in native_variants:
                conditions = sorted(behavior + native, key=_condition_token)
                key = segment_key(conditions)
                size = int(segment_mask(members, native).sum())
                if not size:
                    continue
                label = f"{tier.feature} {level}"
                if native:
                    label += ": " + ", ".join(f"{condition.field}={condition.value}" for condition in native)
                definitions.setdefault(key, (size, label, conditions))
    results = []
    selected = sorted(definitions.items(), key=lambda item: (-item[1][0], item[0]))[:5]
    for key, (size, label, conditions) in selected:
        revenue = frame.loc[segment_mask(frame, conditions), "net_revenue_90d"].to_numpy(dtype=float)
        low, high = _mean_interval(revenue)
        results.append(SegmentCandidate(key, label, conditions, size, _mean(revenue), low, high))
    return results

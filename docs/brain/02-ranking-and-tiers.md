# 02 — Ranking and measured tiers

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What
`domain/ranking.py` ranks numeric rule values and derives measured developer feature tiers.
Rules with no finite values joined to finite purchase outcomes remain hypotheses.

## Why
Behavioral differences must survive held-out users before they can consume Adapty attributes.
Ranking describes association. Randomized offer comparisons decide what to show.

## How it works
`rank(matrix, outcome)` aligns by user ID, sorts IDs, and permutes users with NumPy seed 42.
The first floor(0.7 × users) train; the remaining users form the holdout. Nonfinite outcomes
are excluded before splitting; nonfinite feature values are excluded within each split.
Negative outcomes, duplicate IDs/columns, and inconsistent matrix dimensions are rejected.

For each rule, training thresholds are observed values separating `<= threshold` from `> threshold`.
Choose the largest absolute log lift, breaking ties toward the smaller threshold. Both training
groups need at least 150 users. Lift always means mean net revenue above / mean below; down
effects therefore have ratios below 1. The threshold is frozen before examining the holdout.

`Ranking.lift`, `ci_low`, `ci_high`, `n_above`, and `n_below` describe **training users**.
The interval is the 5th/95th percentiles of 400 independent within-group user-bootstrap resamples.
`holdout_lift` describes **held-out users at the unchanged threshold**. Both holdout groups must
also contain at least 150 users. Up passes only when `ci_low > 1` and `holdout_lift > 1`;
down passes only when `ci_high < 1` and `holdout_lift < 1`. Undefined ratios, including zero
denominators in bootstrap resamples, fail closed. Neutral finite values (ratio/CI 1) represent
unestimable results. A constant or undersized training column emits a failed result with
actual training counts at the emitted minimum-value threshold; it has no qualifying comparison.

`derive_tiers(matrix, outcome, rankings, rule_features)` selects the strongest passing rule
for each explicitly mapped developer feature. Candidate cut pairs come from the ranking
threshold and aligned-value tertiles. All three cohorts must exist, means must increase
low < mid < high, and the low/high 90% bootstrap mean intervals must not overlap. Prefer a
valid pair containing the ranking threshold, then balanced cohort sizes. Tier evidence uses
all aligned users and is descriptive. Failed three-way separation emits `passed=False`.
At most 10 passing features are returned. Boundaries are `<= low_max`, `<= mid_max`, else high.
`Ranking.feature` is a rule key; `FeatureTier.feature` comes only from `rule_features`.
`hypotheses(matrix, outcome)` returns column keys with no finite joinable measurements.

## Contract touched
Uses existing `FeatureMatrix`, `Ranking`, and `FeatureTier` models. No shared contract changes.
The service persists tiers through the existing `TierStore` port.

## How to test
```bash
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" \
  feature-signal:dev pytest -q -p no:cacheprovider \
  tests/unit/test_ranking.py tests/unit/test_ranking_tiers.py
```
Expected: 21 passed. Covers hand-calculated up/down ratios, holdout isolation, noise,
uncertainty, missing values, tier boundaries, feature mapping, and the 10-feature budget.

Replay uses the read-only offline snapshot and an **assumed observation cutoff** of
`2026-11-02T22:45:23Z`, supplied explicitly to `build_outcomes`. Mature users: **12,452**;
mean net revenue in 90 days: **$9.588070**. Results from the unmodified algorithm:

| Rule | Cut | Training lift | Training 90% CI | Holdout lift | Training above/below | Passed |
| --- | ---: | ---: | --- | ---: | --- | --- |
| ai_edits_first_day | 0 | 3.100754 | 2.599294–3.736010 | 2.796197 | 7,529 / 1,187 | yes |
| photos_imported | 38 | 1.157465 | 0.943125–1.364470 | 0.868991 | 359 / 8,357 | no |

Mapping `ai_edits_first_day → editor` yields a passing tier with `low_max=0`, `mid_max=2`.

## Limits / not claimed
Synthetic snapshot evidence does not establish causality. Training threshold selection can
overfit; the holdout sign check is required, and it is not a multiple-testing correction.
Three-tier intervals are descriptive, not a second independent validation. No feature names
receive special thresholds. No I/O, LLM calls, persistence, or attribute writes occur here.

## Status
Done · Next: measured segment candidates.

# 03 — Measured segment candidates

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What
`build_segments(frame, tiers)` returns at most five measured, reproducible segment candidates.
`segment_mask(frame, conditions)` evaluates their raw predicates for randomized-arm analysis.

## Why
Offer comparisons and proposal drafts need the same interpretable cohort definition.

## How it works
Only passing tiers with an available rule column produce candidates. Each tier becomes raw bounds:
low is `rule <= low_max`, mid is `rule > low_max AND rule <= mid_max`, and high is `rule > mid_max`.
The function intersects each cohort with observed tuples of available `platform`,
`subscription_state`, and `country_tier`. It never derives subscription state from revenue or
maps countries to invented country tiers. Columns absent or entirely null are omitted. If no
complete native tuple exists in a tier, a behavioral-only definition remains available.
Partially missing native tuples are excluded when complete observed tuples exist.

The five largest nonempty cohorts win, with stable keys breaking size ties. Candidates may
overlap across features. Sizes count users; each user ID must be unique and nonmissing.
Outcome values must be finite and nonnegative. Rows are sorted by ID before the 400-resample,
seed-42 user bootstrap; `ci_low`/`ci_high` are the 5th/95th percentiles of cohort mean net
revenue in 90 days. Reordering input rows preserves definitions, sizes, means, and intervals.

`segment_key(conditions)` hashes canonical predicates with a readable field prefix. Condition
order and `IN`/`NOT IN` value order do not matter; keys contain at most 50 ASCII characters.
Missing predicate columns fail closed. Predicates are conjoined. Supported operators are
`>`, `>=`, `<`, `<=`, `=`, `==`, `!=`, `IN`, `NOT IN`, `IS NULL`, and `IS NOT NULL`.
Ordinary comparisons exclude null and nonfinite numeric values. Unknown operators raise an error.

## Contract touched
Uses existing `Condition` and `SegmentCandidate` models without a shared-model change.
`SegmentCandidate.conditions` remains a flat list of raw predicates. Behavioral predicates
refer to rule keys; native predicates use only the three explicit baseline field names.
C/B5 can separate native filters by those field names for the existing `adapty_filters` handoff.
The single proposal trigger remains C's `p_segment` condition. This chapter does not add a
compound `Condition` wire format or refer to computed `f_*_tier` columns in offline data.

For example, a candidate for `editor high` contains:
```python
[
    Condition("ai_edits_first_day", ">", 2.0),  # behavioral definition
    Condition("platform", "==", "iOS"),  # native Adapty filter
]
```

## How to test
```bash
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" \
  feature-signal:dev pytest -q -p no:cacheprovider tests/unit/test_ranking_segments.py
```
Expected: 20 passed, covering stable keys, boundary membership, cohort statistics, row-order
invariance, native fields, absent metadata, invalid cohorts, operators, and the five-candidate cap.

The synthetic offline replay at the assumed cutoff `2026-11-02T22:45:23Z` contains platform,
but no baseline subscription-state or country-tier columns. Passing editor cuts are 0 and 2.
The five selected cohorts are:

| Tier / platform | Users | Net ARPU in 90 days | 90% bootstrap CI |
| --- | ---: | ---: | --- |
| high / iOS | 3,700 | $14.3780 | $13.7106–$15.0712 |
| high / Android | 2,753 | $10.7298 | $10.0019–$11.5139 |
| mid / iOS | 2,510 | $7.8768 | $7.2179–$8.5838 |
| mid / Android | 1,790 | $6.0977 | $5.4089–$6.8208 |
| low / iOS | 989 | $4.1322 | $3.2996–$4.8694 |

## Limits / not claimed
Intervals describe observed cohorts, not causal offer effects. The five largest candidates
need not cover every user. Overlapping feature cohorts require C's membership precedence.
No Adapty calls, attribute writes, persistence, or future-state inference occur in this module.

## Status
Done · Next: randomized-arm uplift and insight orchestration.

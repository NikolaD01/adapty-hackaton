# 04 — Randomized offer uplift

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What
Compare documented randomized flow arms within each behavioral segment using mature, fixed-90-day net revenue.

## Why
Behavioral rankings describe different users. Only randomized offer comparisons support choosing an offer.

## How it works
`compare_arms` estimates treatment minus control and a 90% user-bootstrap interval with 400 resamples,
seed 42. `by_segment` keeps the three documented experiments separate. It never compares placement
populations or unknown experiments. Output is oriented toward the higher observed mean: `n_a` counts
`better_arm`, `n_b` counts `worse_arm`. An interval crossing zero is descriptive; the service creates a
draft only when the lower bound is strictly positive and the winning flow is verified published.
The CLI and proposal evidence report refunded paid transactions / paid transactions for both arms.
Zero paid transactions produce an undefined rate (`null`), not a fabricated zero rate.

## Contract touched
None. Existing `Uplift` fields remain unchanged. Refund diagnostics use existing proposal evidence and
reason text, plus CLI output; they are not extra fields in `UpliftOut`.

## How to test
```bash
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev pytest -q -p no:cacheprovider tests/unit/test_uplift.py tests/integration/test_insight_cli.py
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" --mount "type=bind,src=$PWD/../adapty-seed-data-hack/data/offline,dst=/offline,readonly" feature-signal:dev python scripts/train_from_offline.py --data-dir /offline --as-of 2026-11-02T22:45:23Z --analysis
```
The 14 tests cover known positive/negative effects, interval coverage, missing arms, experiment isolation,
refund denominators, deterministic ordering and CLI evidence. The real synthetic snapshot yields:

| Main lifetime arm minus main control | Users (lifetime/control) | Net revenue difference | 90% interval |
|---|---:|---:|---:|
| Five or more first-day edits | 103 / 91 | $4.5539 | [-$1.0172, $10.0706] |
| Zero first-day edits | 89 / 99 | $5.1349 | [$0.5451, $9.1937] |

## Limits / not claimed
On 2026-11-08 the developer explicitly chose **the specified 90-day metric**, with the old
+$14.40 / +$5.36 reference mismatch documented. The earlier all-history calculation was approximately
+$14.39 / +$5.41 and is not the product metric. We do not tune windows or thresholds to reproduce it.
The five-plus-edit main comparison does not establish a positive effect at this confidence level.
The cutoff remains an explicit maximum-install-time assumption; these are synthetic, exploratory
segment estimates, without a multiple-comparison correction or a claim about production users.

## Status
Implemented and tested. The historical benchmark conflict is resolved by the developer's metric decision.

# 01 — Offline outcomes

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What
The CSV adapter and CLI calculate one 90-day net-revenue outcome per mature user, including nonpayers.

## Why
Ranking and randomized offer comparisons need the same observation window and refund treatment.

## How it works
`CsvOfflineDataset` reads the compressed user/transaction tables. `build_outcomes` joins by unique user ID,
keeps users observed for at least 90 days, and sums purchases in `[install_at, install_at + 90 days)`.
A purchase whose refund is known by the explicit observation cutoff contributes zero. This includes
refunds recorded after day 90, as required by the brief's non-refunded-purchase definition; it is not
a cash-flow-within-90-days metric. Refunds after the observation cutoff are not treated as observed.
The frame also contains paid/refunded transaction counts. The CLI prints cutoff, cohort size, mean,
and input SHA-256 hashes. Invalid keys, dates, prices, and duplicate transactions fail explicitly.

## Contract touched
None. The adapter implements the documented B-owned `OfflineDataset` shape. Shared schemas/ports are unchanged.

## How to test
```bash
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev pytest -q -p no:cacheprovider tests/unit/test_insight_offline.py
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" --mount "type=bind,src=$PWD/../adapty-seed-data-hack/data/offline,dst=/offline,readonly" feature-signal:dev python scripts/train_from_offline.py --data-dir /offline --as-of 2026-11-02T22:45:23Z
```
Expected: 14 tests pass; dataset replay reports 12,452 users and mean net revenue $9.588070189527787.

## Limits / not claimed
The dataset is synthetic. The replay cutoff is the maximum install timestamp, an explicit conservative
assumption until the export's true observation cutoff is provided. The program does not silently infer
that date from the wall clock. Historical all-user uplift references are a separate calculation from
this mature 90-day cohort and must not be used as its acceptance values without review.

## Status
Implemented, tested, and independently reviewed. Full suite: 115 tests pass; Ruff passes.
Next: B2 ranking and tiers.

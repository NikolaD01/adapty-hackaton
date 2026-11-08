# 09 — Relative-clock seed outcomes

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What

`SeedJsonDataset` reads `lumen_dataset.json.gz` and supplies the same user and
transaction frames as the CSV adapter. It supports the first 1000 synthetic users
loaded by A's demo events without changing the existing 90-day accounting.

## Why

The live demo IDs must join their matching purchase outcomes. Seed user index `i`
maps to `lumen_282506_{i:05d}` by default. The `L`-prefixed CSV copies are not this join.

## How it works

`feature_signal/integrations/offline.py:SeedJsonDataset` accepts a gzip JSON path,
required `as_of`, optional decimal-string `run_id` (default `282506`), and positive
integer `limit` (default `1000`). It selects the first `limit` users in file order,
preserving each source index, flattened `attrs`, and experiment metadata including
`platform`, `country`, `placement`, `flow`, and `ab_test`.

The export contains no absolute timestamp for dataset "now". `as_of` is an explicit
UTC arithmetic anchor for offset zero; it does not identify the calendar date of
the export. Install, purchase, and non-null refund offsets are seconds relative to
that anchor. Refund offset `0` is a real observed refund. `usd` becomes `price_usd`;
each user's transaction position becomes `seq`, starting at zero.

Pass the same `as_of` to `build_outcomes`. Maturity and revenue remain invariant
when both anchors shift together. The existing function keeps mature nonpayers,
uses the purchase window `[install, install + 90 days)`, and subtracts refunds
observed by `as_of`, including refunds after the purchase window.

The adapter accepts JSON integer or floating-point offsets and prices. Numeric
strings, booleans, nonfinite numbers, negative prices, invalid timestamps,
duplicate indices, and malformed structures raise `ValueError`. User indices
must be nonnegative JSON integers. It validates all source records, including
those beyond the selection limit. Empty users and transactions retain required
frame columns. Frame methods and the provenance property return copies. The
fingerprint is the SHA256 of the original compressed file.

`attrs` values must be JSON scalars: numbers, strings, booleans, or null. Nested
objects and arrays are rejected. Attribute keys cannot collide with top-level
native metadata or reserved identity, experiment, transaction, and outcome
columns. In particular, attributes cannot overwrite or manufacture `ab_test`,
`flow`, `placement`, `platform`, or `country` when these native fields are absent.

## Contract touched

None. This is an additional input adapter for the existing `build_outcomes`
function. Its provenance reports `dataset_format: seed_json`,
`time_basis: relative_to_dataset_now`, run ID, user limit, and `synthetic: true`.

## How to test

```bash
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$PWD:/app:ro" -w /app feature-signal:dev \
  pytest -q -p no:cacheprovider tests/unit/test_insight_seed.py
```

Expected: `93 passed`.

Read-only replay of `../adapty-seed-data-hack/data/lumen_dataset.json.gz`, with
default run and limit, produced 1000 selected users, 646 selected transactions,
258 mature users, $2446.82 total net revenue, and $9.483798449612404 mean net
revenue in 90 days. Their 90-day windows contain 158 paid transactions and 3
observed refunded transactions. The arbitrary replay anchor was
`2026-05-01T00:00:00Z`.

Compressed source SHA256:
`9943d29ded31266d48cf067ff942723ffcbd2d1e64692871b1f0a63a50acb9dd`.

## Limits / not claimed

This is synthetic seed data. The JSON contains 5000 users from the larger CSV
cohort. The default demo cohort is only its first 1000 users, and only 258 have a
full 90-day window. No calendar export date or production revenue is claimed.
The adapter does not rank signals, infer experimental assignment, or write to
Adapty.

## Status

Done for the input adapter. CLI and service selection are handled separately.

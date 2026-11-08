# 08 — Live values and historical outcomes

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What
Consume A's real `ValueStore.matrix(app_id)` while keeping unmeasured behavior separate from evidence.

## Why
A matching user identifier or similar rule name cannot establish a valid historical measurement.

## How it works
Live joins require **both** explicit `user_id_map` membership and membership in `live_outcome_rules`.
The caller must verify that those rule values represent the intended baseline measurement/window
for the supplied outcome snapshot. Defaults are empty: a current rolling-seven-day rule is not an
alias for `ai_edits_first_day`. Even identical user IDs require an explicit verified identity mapping.
Newly installed `L`-prefixed seed copies are not mature historical profiles.

`live_dataset` supplies seed-JSON purchase outcomes separately from the full offline CSV dataset.
Both use the same fixed 90-day calculation; fallback retains the CSV source.

Unverified and missing-valued rules appear in `hypotheses`, never in rankings or tiers. If no verified
outcomes join, the service uses historical columns and returns the actual `source: offline`. A historical
column whose name collides with an unverified live rule is excluded to avoid contradictory evidence.
With some verified users, a small cohort stays `source: live` and fails the unchanged ranking minimum;
it does not quietly borrow extra historical users. Rejected/unknown users never acquire another user's
revenue. Outcome and experiment metadata cannot be overwritten by a rule column.

Verified live rules are associated with developer features through A's `RuleRepo`. Proposal evidence
labels the demo data synthetic and records requested/effective source, cutoff and fixed 90-day window.

## Contract touched
No shared fields changed. The existing source/hypotheses fields and proposal evidence carry the result.
The host's runtime metadata is an explicit assertion of identity/window provenance, not inferred data.

## How to test
```bash
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev pytest -q -p no:cacheprovider tests/service/test_insight_service.py tests/integration/test_insight_api.py
```
Tests include a verified 3,000-user signal, a 200-user insufficient cohort, missing/unknown identities,
new seven-day rules with finite values, colliding IDs/rule names, missing values and offline fallback.
An API integration test writes the verified fixture through the real SQLite `ValueRepository` and reads
passing rankings/tiers through the real endpoint. No network is used.

## Limits / not claimed
The real A8 replay was checked with 1000 input users and 25,226 accepted events. A produces values for
996 users with events, across 17 rules. The JSON outcome adapter retains 258 mature users, mean net
revenue $9.483798 per user. The configured synthetic replay returned 17 live rankings, zero passing
rankings, and zero tiers: the full-window cohort cannot meet 150 users per side. The minimum remains
unchanged. Synthetic recent events generated from historical attributes are not production baseline
measurements; their replay eligibility was explicit in this verification, not inferred by default.
The JSON has no absolute dataset-now date; its supplied anchor is arithmetic only.

## Status
Implemented and tested against A's real demo generator, API, value repository and tier repository,
with the JSON purchase outcomes supplied by A. B8's real-port check is complete; passing live tiers
are not claimed for this cohort. C's production runtime composition/activation remains a separate handoff.

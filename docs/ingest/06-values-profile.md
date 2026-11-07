# 06 — Values, feature profile and TierStore

**Area:** A · **Branch/PR:** `ingest/values-profile` · **Date:** 2026-11-08

## What
Rules become numbers per user. `POST /values:recompute` runs every rule for every user, `GET /values`
pages them, `GET /users/{id}/features` returns the user's feature profile (values grouped by feature +
tier), and ingest refreshes a user's values right after their events are stored. B and C get the
`ValueStore` (`matrix()`) and `TierStore` ports.

## Why
The profile is the "JSON per feature" that stays with us; B ranks the matrix, C turns passed tiers and
segments into Adapty attributes (`docs/plan.md`, "From values to tiers and a segment").

## How it works
- `services/value_service.py:ValueService.recompute_users(app_id, users)` — each user's whole history ×
  every rule through `domain/rules.py:apply`, upserted into `user_values`. `recompute_all` = every user
  with events.
- Ingest (`services/ingest_service.py`) calls `recompute_users` for the batch's users after the commit and
  **before** the membership sync, so C always reads fresh values.
- `repositories/values.py:ValueRepository` — `put_many` (upsert), `matrix()` → `FeatureMatrix` (sorted
  users × sorted rule keys, missing = 0), `page()` (offset cursor), `of_user()`.
- `repositories/tiers.py:TierRepository` — `put_many` replaces the app's tiers with the latest run;
  `list()`. The profile shows `tier` only for `passed` tiers: `FeatureTier.tier(value of tier.rule_key)`.

## Contract touched
`POST …/values:recompute`, `GET …/values`, `GET …/users/{id}/features`; ports `ValueStore`, `TierStore`
(`docs/contracts/ports.md`). No change.

## How to test
```bash
make test-docker
curl -s "localhost:8000/v1/apps/$APP/users/u_42/features"
curl -s -XPOST "localhost:8000/v1/apps/$APP/values:recompute"
```
Expected: `82 passed`; the profile lists `ai_generate` with `ai_generate_uses_7d` etc.; recompute returns
`{"users": N, "rules": M}`.

## Limits / not claimed
Recompute is a full pass (fine for the demo's ~200 users). Values are stored, not versioned.

## Status
Done · Next: A5 SDK, A8 demo events.

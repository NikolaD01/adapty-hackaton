# 01 — Tables and first migration

**Area:** A · **Branch/PR:** `ingest/tables-migration` · **Date:** 2026-11-08

## What
Every table the product needs exists, created by one Alembic migration (`0001`). The SQLite database runs
in WAL mode with foreign keys on, so the dashboard can read while the SDK writes.

## Why
Everyone else builds on these tables: B writes tiers, C stores proposals, decisions, settings and the last
attributes written to Adapty. Event history is the only time axis we have, because Adapty keeps no
attribute history (`docs/plan.md`, "Our tables").

## How it works
- `feature_signal/db/tables.py` — 12 tables:

  | Table | Key | Purpose |
  |---|---|---|
  | `features` | (app_id, key) | feature = group of events, `plans` that include it |
  | `event_types` | action_id (int), unique (app_id, key) | event catalog |
  | `event_type_features` | (action_id, feature_key) | an event may be in several features |
  | `events` | event_id (uuid) | append-only history; index (app_id, customer_user_id, occurred_at) |
  | `user_action_counts` | (app_id, user, action_id) | counters, changed only inside ingest |
  | `rules` | rule_id, unique (app_id, key) | rule definitions (JSON), `source`, `feature` |
  | `user_values` | (app_id, user, rule_key) | computed values |
  | `feature_tiers` | (app_id, feature) | B's measured cut points (TierStore) |
  | `proposals`, `decisions`, `app_settings` | ids / app_id | C's state (nested parts as JSON) |
  | `adapty_attribute_state` | (app_id, user) | last attributes written, so sync sends only diffs |
- `events` stores the integer `action_id`, never the string key. A repeated `event_id` is refused by the
  primary key; ingest (chapter 3) uses that for idempotency.
- `feature_signal/db/session.py:make_engine` turns on `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`.
- `alembic.ini` + `feature_signal/db/migrations/env.py`: the URL comes from `DATABASE_URL`, the async driver
  is swapped for the sync one, batch mode is on for SQLite. `docker compose up api` runs
  `alembic upgrade head` before starting.

## Contract touched
Tables only (`docs/contracts/api.md` field names). No endpoint changes.

## How to test
```bash
make test-docker          # or: docker compose run --rm test
make migrate              # host: creates data/app.db
```
Expected: `28 passed`; `tests/integration/test_db_tables.py` upgrades an empty DB, runs `alembic check`
(models = migrations), round-trips one row per table, and proves duplicate `event_id` and duplicate
event key per app are refused.

## Limits / not claimed
No repositories yet (chapters 2–6). New column = new migration; never edit `0001` after merge.

## Status
Done · Next: A2 features + event catalog API (default rules per feature).

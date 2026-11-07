# 02 — Features and event catalog

**Area:** A · **Branch/PR:** `ingest/features-catalog` (on top of `ingest/tables-migration`) · **Date:** 2026-11-08

## What
The developer can define features (groups of events, with the plans that include them) and register
event types that belong to one or more features. Every feature gets its default values automatically and
they stay in step when events join or leave it.

## Why
Measurement needs values per feature from minute one; the AI only adds composed values on top
(`docs/plan.md`, "Default values, and AI suggests what else is worth computing").

## How it works
- `domain/rules.py:default_rules(feature_key, feature_name, event_keys)` (pure) → `<f>_uses_total`
  (count), `<f>_uses_7d` (count, 7 d), `<f>_days_active_7d` (days_active, 7 d), `<f>_used_<event>`
  (exists) per event. No events → no rules yet.
- `services/catalog_service.py:CatalogService` — `register_feature` upserts and refreshes defaults;
  `register_event_type` refuses unknown feature keys (`UnknownFeaturesError` → `422 unknown_feature`),
  upserts the event and its feature links, then refreshes defaults of every feature it joined **or left**.
- `repositories/rules.py:upsert_default` never overwrites a rule saved by a human or the AI under the
  same key. Stale `used_<event>` rules stay (their history is still valid).
- `repositories/{features,event_types,rules}.py` implement the `FeatureRepo`, `EventTypeRepo` and
  `RuleRepo` ports. `db/session.py:get_session` is the per-request session dependency.
- `db/tables.py:UtcDateTime`: SQLite drops time zones; this type stores UTC and returns aware UTC, so
  every API time ends in `Z`/`+00:00` as the contract says. Naive datetimes are refused.

## Contract touched
`POST/GET /v1/apps/{app_id}/features`, `POST/GET /v1/apps/{app_id}/event-types` (`docs/contracts/api.md`).
Shared test fixtures `tests/integration/conftest.py`: `db_url` (migrated SQLite file) and `api`
(TestClient on that database) — any area can use them.

## How to test
```bash
make test-docker
curl -s -XPOST localhost:8000/v1/apps/$APP/features -H 'content-type: application/json' \
  -d '{"key":"ai_generate","name":"AI generation","description":"Generate an image","plans":["premium"]}'
curl -s -XPOST localhost:8000/v1/apps/$APP/event-types -H 'content-type: application/json' \
  -d '{"key":"generate_click","name":"Generate","description":"User clicked generate","features":["ai_generate"]}'
```
Expected: `39 passed`; the curls return the saved objects (`200`). Three events in `ai_generate` → 6 default rules.

## Limits / not claimed
`GET /rules` and rule evaluation come in chapter 5 (A6). Removing a feature is not supported (not needed for the demo).

## Status
Done · Next: A3 idempotent ingest, A6 rules engine.

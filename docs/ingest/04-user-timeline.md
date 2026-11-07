# 04 — User timeline

**Area:** A · **Branch/PR:** `ingest/user-timeline` · **Date:** 2026-11-08

## What
`GET /v1/apps/{app_id}/users/{customer_user_id}/timeline?limit=50` returns a user's last events, newest first.

## Why
The demo shows a click arriving in seconds (D's side panel); it also makes ingest easy to debug.

## How it works
`repositories/events.py:EventRepository.recent` orders by `occurred_at` (phone time) desc, then `received_at`
desc; `limit` 1–200 (422 outside). Each item has `event_id`, `key`, `occurred_at`, `received_at`, `props`.

## Contract touched
`GET …/users/{customer_user_id}/timeline` (`docs/contracts/api.md`). None changed.

## How to test
```bash
make test-docker
curl -s "localhost:8000/v1/apps/$APP/users/u_42/timeline?limit=5"
```
Expected: `50 passed`; the curl returns `{"customer_user_id":"u_42","items":[…]}` newest first.

## Limits / not claimed
A late (offline-buffered) event appears at its phone time, not at the top.

## Status
Done · Next: A6 rules engine.

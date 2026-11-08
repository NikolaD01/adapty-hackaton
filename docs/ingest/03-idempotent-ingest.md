# 03 — Idempotent event ingest

**Area:** A · **Branch/PR:** `ingest/idempotent-events` · **Date:** 2026-11-08

## What
`POST /v1/apps/{app_id}/events` stores a batch of up to 500 events. A repeated `event_id` (a retry after
a timeout, or the same id twice in one batch) is a duplicate: stored once, counted once. After the
commit the fast loop (`MembershipSync`) runs in the background for the users in the batch.

## Why
Phones retry and buffer offline. Without idempotency the history and the counters drift, and every value
built on them lies (`docs/plan.md`, "Our tables").

## How it works
`repositories/events.py:EventRepository.record_batch` in one transaction:
1. map keys to integer `action_id`s; unknown keys → `unknown_keys`, not stored;
2. drop repeats inside the batch (first wins);
3. `INSERT … ON CONFLICT(event_id) DO NOTHING RETURNING event_id` — the returned ids are the rows
   actually inserted;
4. upsert `user_action_counts` only for those rows (`n += k`, `last_ts` = the later of old and new, so late
   offline events don't move it back).
`services/ingest_service.py:IngestService` commits; the route schedules `run_membership_sync` with
`app.state.membership_sync` (set by C; no-op until then; a failure is logged and never fails ingest).
Props validation (numbers, bool, strings ≤100, ≤20 props) is in `schemas/events.py`.

## Contract touched
`POST /v1/apps/{app_id}/events`, `EventSink` and `EventReader` ports. New: the `app.state.membership_sync`
wiring (`docs/contracts/api.md`, Membership sync).

## How to test
```bash
make test-docker
curl -s -XPOST localhost:8000/v1/apps/$APP/events -H 'content-type: application/json' -d '{"events":[{"event_id":"0b6f0c1e-5d1a-4c7e-9a0e-3f0f2b7c9a11","customer_user_id":"u_42","key":"generate_click","occurred_at":"2026-11-07T18:02:00Z","props":{"tokens_left":0}}]}'
```
Expected: `48 passed`; first curl `{"accepted":1,"duplicates":0,"unknown_keys":[]}`, the same curl again
`{"accepted":0,"duplicates":1,"unknown_keys":[]}` (register the feature and event type first, chapter 2).

## Write key (optional)
With `INGEST_API_KEY` set, `POST /events`, `/features` and `/event-types` need `X-Api-Key` (the SDK sends
it with `init({ apiKey })`); reads stay open. Unset = open, as in the local demo.

## Limits / not claimed
The fast loop gets every user of a batch that stored at least one new event. Timeline (`GET …/timeline`) is A4.

## Status
Done · Next: A4 timeline, A6 rules engine.

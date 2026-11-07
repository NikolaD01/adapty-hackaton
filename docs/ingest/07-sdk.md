# 07 — JS SDK

**Area:** A · **Branch/PR:** `sdk/js-track` · **Date:** 2026-11-08

## What
`sdk/js` (`feature-signal-sdk`): `init`, `registerFeature`, `registerEventType`, `track`, `flush`, plus
`setUser`, `pending`, `shutdown`. Same exports and shapes as D's `web/src/sdk-stub.ts`, so the web app
switches by changing one alias.

## Why
The app must report what users do with exactly-once semantics while phones retry and go offline
(`docs/plan.md`, "What the developer tracks").

## How it works
`sdk/js/src/index.ts`: `track` buffers `{event_id: crypto.randomUUID(), customer_user_id, key,
occurred_at: new Date().toISOString(), props}`; a timer flushes every 2 s, or at 20 buffered events.
`flush` posts up to 500 events to `/v1/apps/{app_id}/events`; only on success are those ids removed, so
retries resend the same ids (no double counting). One flush at a time; events tracked meanwhile stay
queued. `cleanProps` enforces the contract limits and drops free text with a warning.

## Contract touched
Client of `POST …/events`, `POST …/features`, `POST …/event-types`. No change.

## How to test
```bash
cd sdk/js && npm install && npm test -- --run && npm run typecheck   # Node 20
```
Expected: `10 passed`, typecheck clean. End-to-end check done against `docker compose up api`: two
`track()` calls → `{"sent":2,"accepted":2,"duplicates":0}`, a 200-char `prompt` prop dropped, the timeline
shows both events and the feature profile shows `ai_generate_uses_7d: 2`.

## Limits / not claimed
The buffer lives in memory: closing the tab before a flush loses unsent events (no localStorage queue).
No auth header yet (demo backend is open).

## Status
Done · Next: A8 demo events.

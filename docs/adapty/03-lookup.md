# 03 — Served-flow lookup

**Area:** C · **Branch/PR:** `adapty/lookup` · **Date:** 2026-11-08

## What
`POST /v1/apps/{app_id}/lookup` tells which flow Adapty serves to up to 10 users at a placement, right now.

## Why
The SDK cache serves the old flow until the profile refreshes, so the demo proves a segment change with this call.

## How it works
1. `integrations/adapty/lookup.py:AdaptyFlowLookup.served` reads the profile (`profile_id`, `segment_hash`).
   Unknown user (404) → empty hash and no flow, not an error.
2. It calls `.../api/v1/sdk/in-apps/<key prefix>/flow/variations/<placement>/<md5(placement:segment_hash)>/?disable_cache`
   with `Authorization: Api-Key` and the `ADAPTY-SDK-*` headers. With several variations the heaviest one is reported.
3. `services/lookup_service.py:LookupService` asks all users concurrently; `api/v1/lookup.py` maps to `LookupOut`.
   The lookup comes from `app.state.flow_lookup` (tests) or is built once from settings.
4. Other Adapty errors → `502 adapty_lookup_failed`, never containing the secret.

## Contract touched
`POST /v1/apps/{app_id}/lookup` as in `docs/contracts/api.md`; port `FlowLookup` unchanged.

## How to test
```bash
docker compose run --rm test
```
Expected: `135 passed`, `39 tasks, 0 problems`. Manual (2026-11-08, Lumen app): three users on placement `main`
all return `Main - 3 plans` with the same `segment_hash`, because no segment of ours exists yet.

## Limits / not claimed
- It shows the flow for the segment hash, not what a phone renders. Platform is fixed to iOS.
- The "two users, two flows" proof needs C4 (segment + audience) and is done there.

## Status
Done · Next: C3 — proposals store, API and settings

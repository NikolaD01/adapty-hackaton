# 04 — Lumen demo access and tracking

**Area** D · **Branch** `web/lumen-tracking` · **Date** 2026-11-08

## What

The Lumen demo checks the HD export plan in the catalog and uses the agreed free seed profile. The other profile can export in full resolution when its access level matches the catalog.

## Why

The walkthrough needs to show a real event and feature value changing when an export is blocked.

## How it works

The SDK records the attempt for both profiles and adds the blocked event only when the plan check fails. A successful flush refreshes both activity panels. The photo ID and free edit quota stay with the selected user during the demo session.

## Contract touched

Reads features, timeline and feature profile. Sends the existing event batch through the JavaScript SDK.

## How to test

```sh
cd web
npm test -- --run src/test/routes.test.tsx
npm run build
```

Expected 15 tests pass. The free user sends an attempt and a blocked event. The Premium user sends only an attempt.

## Limits

Demo entitlement values are fixtures. Events are labeled synthetic. Set up the Lumen catalog before running live mode.

## Status

D4 complete. D7 tracks the full live flow.

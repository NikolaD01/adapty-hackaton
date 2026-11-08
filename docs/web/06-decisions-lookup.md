# 06 — Decisions and flow lookup

**Area** D · **Branch** `web/decisions-lookup` · **Date** 2026-11-08

## What

See who made each decision and inspect the activation steps. Compare two users' returned flows at one placement.

## Why

The operator can verify the experiment action and check which content Adapty returns.

## How it works

Proposal links open the matching decision log or prefill the placement in Lookup. Lookup groups results by customer user ID. It displays the audience, segment hash and available A/B arms when the server returns them. A standalone flow uses the original name and ID fields.

## Contract touched

Reads decisions with an optional proposal filter and sends the existing lookup request with two customer user IDs.

## How to test

```sh
cd web
npm test -- --run src/test/decisions-lookup.test.tsx
npm run build
```

Expected five tests pass. Selecting an entry in decision history shows its execution steps. A failed decision shows its error, reverse-ordered results match the correct user, duplicate IDs are rejected, and an A/B result shows both arms.

## Limits

The preview returns synthetic flows. In a live test the SDK selects the arm on the device. The server lookup can show the audience and available arms.

## Status

D6 complete. D7 tracks live integration and D8 tracks rehearsal.

# 06 — Decisions and flow lookup

**Area** D · **Branch** `web/decisions-lookup` · **Date** 2026-11-08

## What

See who made each decision and inspect the activation steps. Compare two users' returned flows at one placement.

## Why

The operator can verify the experiment action and check which content Adapty returns.

## How it works

Proposal links open the matching decision log or prefill the placement in Lookup. Lookup renders results by customer user ID and shows the flow name, flow ID and segment hash.

## Contract touched

Reads decisions with an optional proposal filter and sends the existing lookup request with two customer user IDs.

## How to test

```sh
cd web
npm test -- --run src/test/decisions-lookup.test.tsx
npm run build
```

Expected three tests pass. A failed decision shows its error, reverse-ordered API results match the correct user, and duplicate IDs are rejected.

## Limits

The preview returns synthetic flows. In live mode both users can receive the control flow because Adapty assigns test arms.

## Status

D6 complete. D7 tracks live integration and D8 tracks rehearsal.

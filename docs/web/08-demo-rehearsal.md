# 08 — Dashboard rehearsal

**Area** D · **Branch** `web/demo-rehearsal` · **Date** 2026-11-08

## What

The dashboard preview supports the complete operator walkthrough at 1280 × 800. Unhandled preview API requests stay disconnected from the live server.

## Why

The walkthrough needs a stage-ready fallback when the real Brain or Adapty account is unavailable.

## How it works

1. Open the Lumen demo as the free user. Try an AI edit and full-resolution export, then show the timeline and feature profile.
2. Open Metrics, request a suggestion, and accept the blocked-export rule.
3. Open Insights and run it. Show the held-out ranking, the unmeasured HD hypothesis, and the separate historical A/B comparison in 90-day net revenue per user after refunds.
4. In Proposals, keep Human mode, adjust the holdout, and approve the preview proposal. Open its decision log.
5. Compare the two returned flows at the same placement. In the preview, the names and segment hashes come from fixtures.

## Contract touched

None. The preview exercises the same request shapes and leaves the live API unchanged.

## How to test

From a POSIX shell:

```sh
cd web
npm ci
npm test -- --run
npm run build
VITE_USE_MOCKS=true npm run dev
```

Expected: 42 tests pass and the build succeeds. Open `http://localhost:5173/dashboard/events` at 1280 × 800 and follow the steps above in the same tab. The **Mock preview** banner stays visible when switching routes.

## Limits

The backup recording contains the labeled mock walkthrough. The real activation and the team rehearsal are tracked separately by D7 and S3.

## Status

The mock rehearsal completed in 3 min 3 s at 1280 × 800. The backup WebM played at the same resolution. See [live verification](07-live-verification.md) for the remaining real-account checks.

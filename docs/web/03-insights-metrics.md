# 03 — Insights and Metrics

**Area** D · **Branch** `web/insights-metrics` · **Date** 2026-11-08

## What

Run Insights and inspect measured signals, tiers, candidate segments, and historical randomized uplift. Ask for rule suggestions and save selected definitions.

## Why

The dashboard shows which observations passed the holdout check and which new rules still need an experiment.

## How it works

Rankings display the training confidence interval alongside the holdout ratio. Results show the actual source returned by the server. Metrics sends the exact suggested rule to the rules endpoint and refreshes the rule list after acceptance.

## Contract touched

Uses the Insights, rule suggestion, rule write and value read routes. Backend configuration errors are visible in live mode.

## How to test

```sh
cd web
npm test -- --run src/test/insights-metrics.test.tsx
npm run build
```

Expected five tests pass. The rule body is preserved, an offline fallback is labeled correctly, and both configuration errors are explained.

## Limits

The preview renders synthetic fixtures. The live result depends on the app-scoped Brain runtime and model provider.

## Status

D3 complete for the dashboard. D7 tracks live runtime verification.

# 02 — Proposal review and controls

**Area** D · **Branch** `web/proposals` · **Date** 2026-11-08

## What

Review a proposal and its evidence, edit a draft, approve or reject it, and change the app decision mode.

## Why

The operator needs to inspect the audience and offer before an experiment changes delivery.

## How it works

The proposal card separates behavioral membership predicates from Adapty filters. It displays the expected net effect, confidence interval, holdout and edit history. Approval uses the returned lifecycle status, and a flow awaiting publication can be resumed after the operator publishes it in Adapty.

## Contract touched

Uses the proposal list, edit, approve and reject routes and app settings. The edit form sends only changed fields allowed by the PATCH schema.

## How to test

```sh
cd web
npm test -- --run src/test/proposals.test.tsx
npm run build
```

Expected 12 tests pass. A pending approval disables its action, an edited holdout is saved, and switching mode preserves the existing limits.

## Limits

The preview uses in-memory state. A real approval needs the server's configured Adapty account and a team-approved placement.

## Status

D2 complete. Next is Insights and Metrics.

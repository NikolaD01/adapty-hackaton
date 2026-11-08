# 05 — Event catalog and activity

**Area** D · **Branch** `web/event-catalog` · **Date** 2026-11-08

## What

Register features and event types, link an event to up to five features, and inspect each feature's activity.

## Why

The team can declare which events the SDK tracks and see the resulting usage for a demo profile.

## How it works

The forms send the catalog schema and refresh the feature, event and rule lists after a write. The activity picker shows each feature's seven-day usage value for the selected user.

## Contract touched

Uses GET and POST for features and event types. The activity counter reads the existing default rule value from the user feature profile.

## How to test

```sh
cd web
npm test -- --run src/test/events.test.tsx
npm run build
```

Expected two tests pass. The feature and event payloads match the API, and the usage counter changes with the selected user.

## Limits

The counter measures the selected profile. A dash means the API did not return a value.

## Status

D5 complete. Next is decision history and flow lookup.

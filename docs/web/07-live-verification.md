# 07 — Live API verification

**Area** D · **Branch** `web/live-verification` · **Date** 2026-11-08

## What

The dashboard defaults to live API calls. The preview is opt-in and carries its own label.

## Why

The demo needs to distinguish a real request from a preview and show where server configuration is missing.

## How it works

- The production build uses the existing app-scoped API and the proposal routes at `/v1/proposals/{id}`.
- A fresh FastAPI process on a disposable SQLite database served an eight-user Lumen seed. With mocks disabled, Chrome registered an event type, submitted a two-event HD export batch through the SDK, and observed the profile counter rise by two.
- Proposal and decision reads worked on that server. Insights showed the missing Brain runtime and Metrics showed the missing model provider.

## Contract touched

The existing contract is used as written. HTTP 501 displays **Coming soon**. HTTP 503 displays a configuration message when the API identifies the missing service.

## How to test

Start the backend and seed data using the root README. From a second terminal with a POSIX shell:

```sh
cd web
npm ci
VITE_USE_MOCKS=false npm run dev
```

Expected: Events reads the real catalog. The Lumen demo submits a blocked export for the free profile, and the profile updates after the SDK flushes. For a backend on another port, set `VITE_API_BASE` and allow the web origin in the backend CORS configuration.

## Limits

D7 needs a configured Brain runtime for the same app ID, an available model provider for rule suggestions, and an approved Adapty placement with a published offer and control. Use the placement on the proposal when comparing the returned flows. The local check used the ingest API and database only.

C recorded a backend run on the separate `fs_test` placement. That run used a 30-day outcome window and returned audiences and available test arms. The dashboard displays the window from a proposal and, when available, from the proposal linked to an insight run. Lookup supports both response shapes.

## Status

D7 stays open pending the live sequence from a measured rule through Human approval, an Adapty decision and a two-user lookup. The browser preview is ready for rehearsal.

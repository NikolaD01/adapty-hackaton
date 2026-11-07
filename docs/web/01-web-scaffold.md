# 01 Web scaffold and Adapty Overview

**Area D** · **Branch** `web/scaffold` · **Date** 2026-11-07

## What

The Vite app renders the Adapty Overview reference at `/` using static HTML, CSS and SVG charts.
Behavioral Targeting opens the Events placeholder. Overview and the Adapty logo link to `/`.

## Why

The static shell gives the team a consistent place to add behavioral targeting screens and lets us
review the dashboard before connecting API calls.

## How it works

- `web/src/app/` owns routes, the query provider and the dashboard layout.
- `web/src/features/` owns screen components and fixtures specific to a feature. Overview charts
  share a card and an SVG plot. The axis labels use HTML so their font size stays independent of the
  plot width. Chart values live in a separate fixture.
- `web/src/shared/`, `types/` and `styles/` hold reusable UI, environment configuration, shared
  TypeScript types and global styles. Keep page logic in the feature that uses it.
- `web/src/mocks/` owns the shared MSW handlers and separate browser and Node entry points.
  The SDK alias points at `sdk-stub.ts` until Role A's A5 is ready.
- `/dashboard` redirects to `/dashboard/events`. The other feature routes are
  `/dashboard/metrics`, `/dashboard/insights`, `/dashboard/proposals`, `/dashboard/decisions`,
  and `/dashboard/lookup`. The Lumen placeholder is at `/demo`.

## Contract touched

The test exercises the mock for `GET /v1/apps/{app_id}/event-types` from the v1 API contract.
The browser Overview uses data from the design reference.

## How to test

Use Node 20.19 or later in the Node 20 line, as in CI. Run these commands from the repository root.

```sh
cd web
npm ci
npm test -- --run
npm run build
npm run dev
```

Open `http://localhost:5173/`. Expect four charts and a sidebar link to Events. The desktop sizing
comes from the rendered Adapty Overview. It uses Inter, a 240 CSS px sidebar, a 48 CSS px top bar,
14 CSS px control text, 40 CSS px controls and 200 CSS px cards. Compare the 1906 × 920 px reference
at 125% scale, then check Overview and Events for horizontal overflow at 1280, 714 and 320 CSS px.
The narrow preview uses the icon rail to keep the charts in view. [Adapty Overview reference](adapty-admin-reference.png)

The local defaults in `web/.env.example` target the Lumen app and `http://localhost:8000`.
Set `VITE_USE_MOCKS=false` to disable the development service worker integration.

## Overview style measurements

These desktop values come from the rendered Adapty Overview. Dimensions use CSS pixels.

| Area | Measurements |
| --- | --- |
| Body | Inter, 14 px text, 21 px line height, `#111111` text, white background |
| Sidebar | 240 px wide, 36 px rows, 20 px icons, 16 px icon gap, 6 px row radius, `#f3f3f3` selected row |
| Top bar | 48 px high, 24 px horizontal inset, 28 px app avatar |
| Headings | Overview at 24/28 px and weight 600. Section heading at 16/24 px and weight 600 |
| Controls | 40 px high, 14 px text and weight 500, 8 px radius, `#b8b8b8` border |
| Metric cards | 200 px high, 16 px padding, 8 px radius, 24 px grid gap, shadow `0 1px 8px rgb(1 0 48 / 10%)` |
| Metric labels | Title at 14/18 px and weight 600. Value at 20/24 px and weight 600 |
| Charts | `#696969` axes, `#e7e7e7` grid, `#6720ff` bars at 55% opacity |
| Getting started | `#f5f5ff` background, 12 px padding, 8 px top corner radius |

## Limits

The chart values and toolbar are static. The feature pages are route placeholders.
The screenshot guides visual review. The app renders the interface from components.

## Status

Chapter 1 is in progress. Add the remaining API examples and connect each page to its mock before
marking D1 complete.

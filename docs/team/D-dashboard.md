# Role D — Dashboard & Demo (frontend)

**Mission:** one page that looks like a new Adapty dashboard page (Adapty has no plugin API, the brief
allows a prototype that reads real data), plus a tiny demo app that generates events. You work against
mocks from minute one and switch to the real backend per endpoint as it lands.

## You own
`web/**` only. You consume `docs/contracts/api.md` and `sdk/js` (owned by A).

## Stack
React 18 + Vite + TypeScript, Tailwind, TanStack Query, React Router, MSW for mocks (handlers written
from the contract examples), Vitest + Testing Library. Env: `VITE_API_BASE` (default `http://localhost:8000`),
`VITE_USE_MOCKS=true|false`, `VITE_APP_ID=c6c7bdd1-1010-4343-8b29-837a77793cab`.
Style: neutral, Adapty-like (white cards, left sidebar, one accent color). No component library needed.

## Screens (routes)
1. `/demo` — fake Lumen app: buttons **Import photo**, **Remove background**, **AI enhance**, **Export**,
   **Export in full resolution** (shows "Pro only"), user switcher (2–3 seed ids). Each click calls
   `track()` from the SDK; a side panel shows the last events (from `/users/{id}/timeline`).
2. `/dashboard/events` — event catalog (`GET /event-types`) + live counter.
3. `/dashboard/metrics` — rules list + **Suggest with AI** (`POST /rules:suggest`) → suggestion cards
   with rationale → **Accept** (POSTs the rule) / dismiss.
4. `/dashboard/insights` — run (`POST /insights:run`), rankings table (feature, threshold, direction,
   lift with CI bar, holdout, passed ✓/✗), segments, uplift per segment with CI.
5. `/dashboard/proposals` — the core screen. Card per proposal: finding, rule (trigger, condition,
   action), what changes on the paywall, expected effect ± CI, holdout %, reason; buttons
   **Approve / Edit / Reject**. Edit = form for the PATCH whitelist only (threshold/condition value,
   holdout %, flow, cooldown). Status chips `draft/approved/executing/live/failed/rejected`.
   Mode toggle **Human / Autopilot** (`GET/PUT /settings`), autopilot shows a warning banner.
6. `/dashboard/decisions` — decision log with step-by-step results and `decided_by` badge.
7. `/dashboard/lookup` — pick two users + placement → side-by-side served flow names (the demo finale).

## Chapters
1. Scaffold (Vite, Tailwind, router, Query, MSW with all contract examples) — *done when* every route renders with mocks.
2. Proposals screen with approve/edit/reject against mocks (state transitions in the mock).
3. Insights + metrics screens.
4. Demo app with the real SDK (after A's chapter 4).
5. Switch endpoints to the real backend one by one (`VITE_USE_MOCKS=false`); 501 → "coming soon" chip.
6. Lookup screen + polish for the demo (keep it fast and readable at 1280×800).

## Tests you must have
Proposal card renders each status · edit form sends only whitelisted fields · approve button disabled
while executing · 501 shows "coming soon" · demo button calls `track` with the right key.

## Pitfalls
- Don't promise two rendered paywalls: Adapty flows don't render in a browser → show flow names from `/lookup`.
- Never show conversion alone; show net revenue (90 d) and refunds.
- Keep mocks in sync with `docs/contracts/api.md`; if the contract changes, update handlers in the same PR.

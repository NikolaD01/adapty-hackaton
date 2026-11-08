# 16 — Autopilot that really launches (mode switch and insight runs)

**Area:** C · **Branch/PR:** `adapty/autopilot-launch` · **Date:** 2026-11-08

## What
The Human/Autopilot choice now works end to end. Switching the mode to Autopilot launches the waiting drafts, and
an insight run in Autopilot mode launches its new drafts. Before, autopilot ran only on `POST /proposals`, so the
dashboard switch and B's drafts did nothing.

## Why
`docs/plan.md` (Human and Autopilot): in Autopilot the system starts the A/B test by itself, within preset limits.
The live run showed the gap. The mode was switched to Autopilot and nothing started. Then all four drafts were
approved by hand, and three of them targeted the app's real `onboarding` placement. That approval was stopped by
restarting the API before any segment or test was created.

## How it works
- `services/autopilot_service.py`
  - `AutopilotService(..., allowed_placements=None)`: a draft for a placement outside the set is skipped and waits
    for a human.
  - `run_autopilot(session_factory, activation_factory, app_id, allowed)`: one pass in its own session, for work after
    the response. It logs errors instead of losing them.
  - `LaunchingSink`, B's sink in the running app:
    - It applies a placement map, then stores only new drafts. The key is segment, placement and offer flow, so a
      repeated insight run does not queue the same offer twice.
    - It then starts an autopilot pass in the background, which does nothing in Human mode.
- `api/v1/settings.py`: `PUT /settings` with `mode: autopilot` adds the pass as a background task after the answer.
- `api/v1/proposals.py`:
  - `POST /proposals` also respects the placement limit.
  - `autopilot_job` builds the pass from the same Adapty commands and fast loop as a human approve.
- `integrations/adapty/brain_wiring.py`, demo settings:
  - `DEMO_PLACEMENT_MAP = {"main": "fs_test"}`. The test placement's default flow, "Main - 3 plans", is main's
    control, so the test compares what the evidence measured.
  - `AUTOPILOT_PLACEMENTS = {"fs_test"}`, registered as `app.state.autopilot_placements` for both app ids.
    Drafts for `onboarding` or `settings_upgrade` stay for a human.

## Contract touched
No shape change. `PUT /v1/apps/{app_id}/settings` now has a side effect: switching to autopilot launches eligible
drafts, within `max_live_proposals` and `min_holdout_pct`. Publishing a flow is still never reachable.

## How to test
```bash
docker exec adapty-hackaton-api-1 python -m pytest -q tests/integration/test_autopilot.py tests/unit/test_brain_wiring.py
```
Expected: all pass. The new tests cover:
- the placement limit;
- the sink moving `main` drafts and scheduling one pass;
- a repeated insight run creating nothing new;
- the mode switch launching a draft, respecting the limit, and doing nothing in Human mode;
- the demo wiring.

Full suite: `549 passed`.

Live check (2026-11-08, Human mode): an insight run after the restart created no duplicate drafts. The four drafts
stayed: `pr_0bc0514392` on `fs_test`, and three on `onboarding`.

## Limits / not claimed
- `allowed_placements` and the placement map are demo settings in `brain_wiring.py`. They are not in the settings
  API, so a real deployment would need a contract change to expose them.
- The pass runs inside the API process. A restart in the middle of a pass leaves a proposal in `executing`, and
  there is no `live → stopped` transition either. Both are fixed by hand today.
- Proposals that target the same segment share one `p_segment` key. Autopilot launches them one by one, within the
  limit.

## Status
Done · Next: switch to Autopilot in the dashboard and verify `pr_0bc0514392` goes live on `fs_test` (segment,
A/B test, lookup), then the chapter on the 60-day run.

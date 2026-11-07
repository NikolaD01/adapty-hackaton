# 08 — Autopilot mode

**Area:** C · **Branch/PR:** `adapty/autopilot` · **Date:** 2026-11-08

## What
In `autopilot` mode new drafts are approved by the system itself, inside preset limits. Publishing a flow stays human.

## Why
The plan's second mode: the system starts the A/B test by itself, with the same audit trail as a human decision.

## How it works
1. `services/autopilot_service.py:AutopilotService.run(app_id)` does nothing unless settings say `autopilot`.
2. Drafts go most valuable first (`expected_effect.diff`). It stops when `max_live_proposals` is reached; `live`, `executing`
   and `awaiting_publish` proposals use a slot (also ones a human launched), a failed one does not.
3. A holdout below `min_holdout_pct` is raised to it before launching; the change is recorded in `edits`.
4. Each launch is `ActivationService.approve(id, decided_by="autopilot")` (C4): decision action `autopilot_start`,
   `mode_at_decision` `autopilot`. There is no code path to `flows publish`; a new AI paywall waits as `awaiting_publish`.
5. Triggers: `POST /apps/{app_id}/proposals` runs autopilot after storing the drafts and answers with their new status;
   `AutopilotSink` (a `ProposalSink`) does the same for drafts B hands over directly. Switching the mode to autopilot does
   **not** launch existing drafts by itself.
6. No model is called anywhere in this chapter, so autopilot needs no AI token.

## Contract touched
`POST /apps/{app_id}/proposals` (response now carries the status after an autopilot launch), settings limits as in
`docs/contracts/api.md`. To use `AutopilotSink` B's insight service must receive it instead of the plain
`ProposalService` (wiring in a shared file, contract-change).

## How to test
```bash
docker compose run --rm test
```
Expected: `219 passed`, `39 tasks, 0 problems` (`tests/integration/test_autopilot.py`, 11 tests).

## Limits / not claimed
- No quality gate beyond the contract limits: a draft with a negative expected effect would also be launched. B only
  drafts measured winners; a guard on `ci_low` would be a contract change.
- Tested with fakes; the real sequence was run by hand once (see `06-activation.md`).

## Status
Done · Next: C8 — paywall draft from the live config

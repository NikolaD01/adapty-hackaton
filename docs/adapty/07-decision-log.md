# 07 — Decision log API

**Area:** C · **Branch/PR:** `adapty/decision-log` · **Date:** 2026-11-08

## What
`GET /v1/apps/{app_id}/decisions` lists who decided what and every step that ran in Adapty, newest first.

## Why
The jury and the team must see that every change was a recorded decision (human or autopilot) and what it did.

## How it works
1. `api/v1/decisions.py` reads `repositories/decisions.py:DecisionRepository.list` (newest first, scoped to the app).
2. Rows are written by C3 (`reject`) and C4 (`approve`, `autopilot_start`); each has `steps: [{step, ok, detail}]`.
3. Optional `?proposal_id=` narrows the list to one proposal (extra, not in the contract; the dashboard can ignore it).

## Contract touched
`GET /apps/{app_id}/decisions` as in `docs/contracts/api.md`. No contract change.
`tests/integration/test_app.py` used `/decisions` as its "unbuilt route" example; it now uses `/insights/latest` (B).

## How to test
```bash
docker compose run --rm test
```
Expected: `207 passed`, `39 tasks, 0 problems` (`tests/integration/test_decisions_api.py`). C's integration tests use
`tests/integration/adapty_helpers.py` (NullPool) so no connection is left open.

## Limits / not claimed
- No paging: the log is small in the demo. Decisions are never edited or deleted.

## Status
Done · Next: C7 — autopilot mode

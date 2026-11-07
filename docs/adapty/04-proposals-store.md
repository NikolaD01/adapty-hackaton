# 04 — Proposals store, edit, reject and settings

**Area:** C · **Branch/PR:** `adapty/proposals-store` · **Date:** 2026-11-08

## What
Proposals from B are stored as drafts. A human can list, edit (whitelisted fields only), reject with a reason,
and read or change the mode (`human` default, `autopilot` with limits).

## Why
Nothing reaches Adapty without a stored, reviewable proposal and an auditable decision (`docs/plan.md`, "Human and Autopilot").

## How it works
1. `services/proposal_service.py:ProposalService` over `repositories/proposals.py` and `repositories/decisions.py`
   (tables `proposals`, `decisions`, `app_settings` come from A).
2. `create_many(app_id, drafts)` is the `ProposalSink` port: a `ProposalDraft` becomes a draft row (`created_by: ai`);
   `POST /proposals` does the same from `ProposalIn`.
3. State machine `ALLOWED_TRANSITIONS` / `check_transition` = the contract: draft→approved|rejected,
   approved→executing, executing→live|failed|awaiting_publish, awaiting_publish→live|failed. Anything else is
   `409 invalid_transition`. C4 uses the same function.
4. `PATCH` allows only `holdout_pct, cooldown_days, flow_id, condition_value, trigger_placement` (unknown field → 422),
   only while `draft` (`409 proposal_not_editable`). Each real change is appended to `edits` as `{at, field, from, to}`;
   a change to the same value adds nothing.
5. `:reject` needs a reason; sets `decided_by: human`, `mode_at_decision` from settings, and writes a decision row.
6. `GET/PUT /settings`: defaults `human`, 3 live proposals, holdout ≥10 %, `allow_publish_flow` always false.

## Contract touched
`GET/POST /apps/{app_id}/proposals`, `PATCH /proposals/{id}`, `:reject`, `GET/PUT /settings`; port `ProposalSink`.
No contract change. One existing test (`tests/integration/test_app.py`) used `/proposals` as its "unbuilt route"
example; it now uses `/decisions` (A should pick a route that stays unbuilt, or drop it, when C5 lands).

## How to test
```bash
docker compose run --rm test
```
Expected: `163 passed`, `39 tasks, 0 problems` (new: `tests/unit/test_proposal_state.py`,
`tests/integration/test_proposals_api.py`).

## Limits / not claimed
- `:approve` and the Adapty side are C4. No dedupe of identical drafts from B.
- Settings are not yet read by anything: autopilot is C7.

## Status
Done · Next: C9 — membership sync

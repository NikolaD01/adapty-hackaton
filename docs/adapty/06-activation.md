# 06 — Activation on approve

**Area:** C · **Branch/PR:** `adapty/activation` · **Date:** 2026-11-08

## What
`POST /v1/proposals/{id}:approve` turns a draft proposal into real Adapty changes and logs every step:
attributes written, segment created, A/B test (control + offer) created and started.

## Why
This is the loop the project is graded on: a proposal ends as a segment and an A/B test with a control arm in Adapty.

## How it works
`services/activation_service.py:ActivationService.approve(proposal_id, decided_by)`:
1. `draft → approved → executing` (state machine from C3), actor and mode saved.
2. `write_attributes`: membership sync for every user with values (an `executing` proposal already counts for `p_segment`).
3. `segments_create`: title `[fs] <segment_key>`, filters `attributes__p_segment@string:IN:<condition.value>` AND each
   `adapty_filters` entry. If a segment with that title exists it is **updated, not duplicated**.
4. `placement_read`: the trigger placement's default flow is the control. Flow A/B defaults are also supported:
   use a copied flow's original active arm, an explicit `control` arm, or the unique other active arm.
   Ambiguous controls fail with `placement_control_ambiguous`; offer == control fails with `offer_equals_control`.
   The default audience and its existing test remain intact.
5. `ab_tests_create` (control `holdout_pct` %, offer the rest, for that segment) and `ab_tests_start` (starting also puts the
   audience on the placement; no separate placement update is needed).
6. `live`. Any `ApiError` or unexpected error: status `failed`, the failing step is logged as `ok: false` with `code` and
   `message` only (no secrets), later steps do not run.
7. `needs_publish` (a new draft flow): stops after step 3 as `awaiting_publish`. After a human publishes the flow in Adapty,
   **approve again** on the same proposal: it checks `flows get` is `published` (`409 flow_not_published` otherwise, nothing
   changes), then runs steps 4–6. Publishing is never called by the service.
8. The decision (`approve`, or `autopilot_start` when `decided_by=autopilot`) is stored with all steps.
9. Failed approvals can retry before A/B creation was attempted, retaining their decision history and reusing segments.
   A previously attempted test or an equivalent active proposal blocks retry. Atomic status/timestamp checks prevent
   concurrent approval or publish continuation from starting duplicate tests.
Providers for the route: `app.state.adapty_commands` / `app.state.membership_sync` (tests) or the real CLI and `SqlMembershipSync`.

## Contract touched
`POST /proposals/{id}:approve`: failed approvals can retry with the guards documented in `docs/contracts/api.md`.

## How to test
```bash
docker compose run --rm test
```
Expected: `203 passed`, `39 tasks, 0 problems` (`tests/integration/test_activation.py`, 17 tests).

Manual, real Adapty (2026-11-08), on a **separate** placement `fs_test` (default `Main - 3 plans`), same arguments the service sends:
`segments create` → segment `[fs] power_editor`; `ab-tests create` → draft 20/80 (control `Main - 3 plans`, offer `Main - Lifetime anchor`);
`ab-tests start` → `live`, and `placements get` then shows the segment audience (flow_ab_test) above the default.
A test profile with `p_segment=power_editor` gets `Main - Lifetime anchor` from `POST /lookup` (own `segment_hash`); a normal user keeps
`Main - 3 plans`. This is the "two users, two flows" proof.

## Limits / not claimed
- The whole service was exercised with fakes; the real CLI was run by hand with the same commands, not through the service
  (the Docker CLI is not logged in).
- Left on the account: placement `fs_test`, segment `[fs] power_editor`, a live A/B test on `fs_test`, and `p_segment` on
  test profile `fs_patchtest_1794068392`. None of them touches the real placements. The CLI cannot delete segments or placements.
- Which arm a user lands in is Adapty's randomization (80 % offer); the profile shows no arm.

## Status
Done · Next: C5 — decision log API

# 09 — Paywall draft from the live config

**Area:** C · **Branch/PR:** `adapty/paywall-draft` · **Date:** 2026-11-08

## What
`POST /v1/proposals/{id}/paywall-draft` makes a new **draft** flow in Adapty: a copy of the proposal's flow config with a new
title. The proposal then points at the draft and waits for a human publish.

## Why
The paywall for a segment should highlight what the group already uses, and never promise what the plan does not include.

## How it works
`services/paywall_service.py:PaywallService.draft(proposal_id, body)`:
1. Only for a `draft` proposal (`409 proposal_not_editable`). Base = `action.flow_id` (a working, published flow).
2. `flows config get` → the config. Offered products = `product_ids`, or every product on the first screen; one that is not
   on the screen → `422 product_not_in_flow`.
3. Plan check (before anything is created): the feature (`highlight_feature` from the body or the proposal) must exist
   (`422 unknown_feature`) and its `plans` must contain a product id **or access level id** of an offered product
   (`products list` gives `access_level_id`), else `422 feature_not_in_plan`.
4. Title = the first non-empty text element of the first screen whose id ends in `T`, in the default locale; none →
   `422 no_title_element`. Only that text changes; the copy keeps every other key (checked).
5. `flows create` (`[fs] <segment_key> <proposal_id>`) → `flows config update` with the copy. Nothing is published.
6. The proposal gets `action.flow_id = <draft>`, `needs_publish = true`, `highlight_feature`, and the change is added to `edits`.
   After a human publishes the flow in Adapty, approving the proposal runs C4 (`awaiting_publish` → `live`).

## Contract touched
`POST /proposals/{id}/paywall-draft` as in `docs/contracts/api.md`. No contract change. `changed_paths` has one entry.

## How to test
```bash
docker compose run --rm test
```
Expected: `232 passed`, `39 tasks, 0 problems` (`tests/integration/test_paywall_draft.py`, 12 tests).
Manual (2026-11-08, real Adapty): the title finder found `Go Premium` on `Main - Lifetime anchor`; a new flow was created and the
edited copy uploaded; `flows get` shows `draft`, `flows config get` shows the new title.

## Limits / not claimed
- Only the title changes. The product list is not edited: removing or adding a plan means changing layout elements, so `product_ids`
  only selects which products count for the plan check. Other locales keep their old title.
- The title comes from the request; this service calls no model (B's `paywall_copy` can write it upstream). No AI token needed.
- A flow whose title is not a `...T` text element is refused rather than guessed. Only the Lumen flows were tried.
- Left on the account: draft flow `[fs] manual paywall draft` (CLI cannot delete flows).

## Status
Done · All C chapters done. Open: wiring `app.state.membership_sync` in `main.py`, B writing `evidence.segment_conditions`.

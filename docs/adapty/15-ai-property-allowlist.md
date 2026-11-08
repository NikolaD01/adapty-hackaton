# 15 — Event properties for AI rule suggestions

**Area:** C · **Branch/PR:** `adapty/ai-property-allowlist` · **Date:** 2026-11-08

## What
B's rule suggestions now see the typed properties the Lumen demo really sends. The model can now suggest quota
rules on `edits_left` and distinct counts on `photo_id`, not only event counts.

## Why
`docs/plan.md`: "AI suggests what else is worth computing", and the quota comes from the app as state. The route
reads `app.state.brain_property_allowlists`, but nothing set it. So the model was told that no property may be used,
although `edits_left` is on 61 % of the stored `ai_enhance` events and `photo_id` is on almost every event.

## How it works
- `integrations/adapty/brain_wiring.py`: `DEMO_PROPERTY_ALLOWLIST` lists event → property → kind:
  `ai_enhance` {`edits_left`: number, `photo_id`: label}; `bg_remove`, `export`, `photo_import` {`photo_id`: label}.
  `synthetic` is left out on purpose: it marks generated data, and a rule on it would measure the generator.
- `configure_demo_brain` registers the allowlist for the demo app id and the Adapty app id. It does so before the flow
  check, because rule suggestions do not need the published flows.
- B's validation is unchanged: a suggested rule may reference only the declared properties, with the declared kind.

## Contract touched
None. It uses the existing `app.state.brain_property_allowlists` hook of `POST /v1/apps/{app_id}/rules:suggest` (B).

## How to test
```bash
docker run --rm --network none -v "$PWD":/app -w /app feature-signal:dev python -m pytest -q tests/unit/test_brain_wiring.py
```
Expected: `10 passed`. The new tests check the declaration for both app ids, the declaration without flows, and that
a quota rule (`count(ai_enhance where edits_left <= 0)`) passes B's validation only with the declaration.

Live check (by hand, 2026-11-08, `gpt-6-luna`, a temporary API on a copy of the database, nothing written).
Before, one suggestion: the share of blocked HD exports. After, two calls returned:
- `ai_enhance_quota_exhausted_uses_total`: `count(ai_enhance where edits_left <= 0)`;
- `ai_enhance_edits_left_latest`: `last(edits_left)`;
- `background_distinct_photos_processed`: `distinct(bg_remove.photo_id)`;
- `hd_export_blocked_attempt_ratio`: `pt_track_hd_export_blocked / export_hd_attempt`.

## Limits / not claimed
- The allowlist is a demo setting for Lumen, like the rest of `brain_wiring.py`. The catalog has no typed-property
  contract yet, so another app needs its own declaration.
- The model chose all-history windows in this check. A 7-day quota rule is still up to a human edit.
- A suggestion is not a finding. Statistics must still pass it before it can become a tier or a segment.

## Status
Done · Next: chapter 16, the 60-day run on `fs_test`.

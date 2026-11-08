# 14 — Real run on Adapty (B → C, all attributes written)

**Area:** C · **Date:** 2026-11-08 · Adapty app `9ccde368…` (`ADAPTY_APP_ID`), demo data app id `c6c7bdd1…`

## What ran
1. Local DB: A's demo events for all 5000 seed users (`load_demo_events.py --users 5000`): 125,548 events, values for 4984 users.
   Loaded with the Adapty key blanked, so ingest could not write while loading.
2. `POST /insights:run {"source":"live"}` through the real API (B wired at startup, 30-day window, explanations on):
   1 tier `background_uses_7d` (cut points 0 and 1), 5 segments, 8 drafts, metric `net_revenue_30d`.
3. Three drafts approved, one per behaviour group, each moved to the test placement `fs_test` first (`PATCH trigger_placement`):
   | Group | Proposal | Platform filter | Attributes written | Took |
   |---|---|---|---|---|
   | `background_uses_7d > 1` | `pr_ae7c7fcdd2` | Android | 7,114 (tier for everyone + `p_segment`) | 122 s |
   | `0 < … ≤ 1` | `pr_92ba5e1ed7` | iOS | 1,264 | 37 s |
   | `≤ 0` | `pr_574a76f5a8` | Android | 1,590 | 150 s |
   Total **9,968 attributes on 4,984 real profiles**, exactly the dry-run prediction. All steps `ok`, all three `live`.

## Checked on Adapty
- 60 random profiles: 59 have `f_background_tier` (one user has no events); tier and `p_segment` agree in every case
  (low → the `≤ 0` key, mid → the `0–1` key, high → the `> 1` key).
- `POST /lookup` on `fs_test`: users in an approved segment show their `[fs] …` audience and the A/B arms (control 20 % `Main - 3 plans`,
  offer 80 % `Main - Lifetime anchor`); an iOS user of the high group shows `All Users`, because only the Android variant of that group
  was approved. That is correct behaviour, not a gap in the code.

## Bugs this run found (fixed, with tests)
1. Lookup always sent platform `iOS`; Adapty validates the segment hash per platform, so Android users in a platform-filtered segment got
   `400 INCORRECT_SEGMENT_HASH_ERROR`. Now it retries with `Android` on exactly that error.
2. Lookup reported the largest arm of an A/B test as if the user saw it. Adapty returns every arm and the SDK picks one; the lookup now
   returns `audience_name`, `ab_test_name` and `arms`.
3. Wiring ran on import of `main.py`, so local test runs reached the Adapty CLI. Moved to the server lifespan.

## Not claimed
- Synthetic data; the 30-day window was chosen after seeing which rules pass (`docs/brain/10-outcome-window.md`).
- Uplift intervals are wide on few paying users (e.g. +$23.93, 90 % interval $3.20–$43.69, from 3 vs 8 paid transactions). Do not present
  them as precise.
- The approved tests run on `fs_test` only; `main`, `onboarding`, `settings_upgrade` were not touched.
- The explanation text: numbers are rendered locally by design; the model chose one of three allowed hypotheses.
- Left on the account: placement `fs_test` with 5 live tests (3 from this run, 2 older probes), their `[fs]` segments, the attributes above.

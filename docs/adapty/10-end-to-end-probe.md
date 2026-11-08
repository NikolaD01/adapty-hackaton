# 10 — End-to-end probe (C with A, B faked)

**Area:** C · **Date:** 2026-11-08 · needs the `contracts/wire-membership-sync` change (ingest drives the sync)

## What
One full pass through the loop on the real Adapty account, with the API running in Docker (real CLI inside, logged in).

## Steps and result (all `ok`)
1. Feature `fs_e2e` (+ event type `e2e_click`) through A's API → default rule `fs_e2e_uses_total` created.
2. Tier written by hand (B is not built yet): `fs_e2e_uses_total` low ≤ 1, mid ≤ 3, high > 3.
3. Proposal created with `POST /proposals`, with `evidence.segment_conditions = [fs_e2e_uses_total >= 3]`, placement `fs_test`.
4. `POST /proposals/{id}:approve` → status `live`; decision steps `write_attributes`, `segments_create`, `placement_read`,
   `ab_tests_create`, `ab_tests_start` all `ok`.
5. Three `e2e_click` events for one test profile through `POST /events`: after each, the user's feature profile showed
   values 1, 2, 3 and tier low, mid, mid (A's recompute works).
6. After the clicks the profile on Adapty held `f_fs_e2e_tier=mid` and `p_segment=fs_e2e`, and its `segment_hash` changed
   (`0269…` → `188f…`): the ingest hook ran the membership sync by itself. `POST /lookup` on `fs_test` returned the offer flow
   for that profile and `Main - 3 plans` for an ordinary user. No errors in the API log.

## Not claimed
- Tiers and the segment rule were written by hand: the real insight run (B) is not built yet, so nothing proves B writes
  `evidence.segment_conditions`. The segment threshold (3) was chosen for the probe, not measured.
- One test profile; the arm Adapty assigned (80 % offer) is random.
- Left on the account: placement `fs_test` with two live tests (segments `[fs] power_editor` and `[fs] fs_e2e`), a draft flow, and
  local DB rows for feature `fs_e2e` (the SQLite file `data/app.db` is not committed).

## Status
Done · Next: real tiers and segment rule from B, then the demo run on the real placement.

# 08 — Demo events for seed users

**Area:** A · **Branch/PR:** `ingest/demo-events` · **Date:** 2026-11-08

## What
`make demo-events` (or `python scripts/load_demo_events.py --users 1000`) registers the Lumen features and
event types and sends a synthetic last-7-days history for the first 1000 seed users, through the real API,
then recomputes values. Every event has `props.synthetic = true`.

## Why
Seed profiles in Adapty have `ai_edits_first_day` but no events. Without a history B has nothing to rank
live and C has nobody to move into a segment.

## How it works
- Features: `background`, `ai_enhance`, `hd_export` (`plans: ["premium"]`), `photo_import`. Events:
  `photo_import`, `bg_remove`, `ai_enhance` (`edits_left` for free users, 10 per day), `export`,
  `export_hd_attempt`, `pt_track_hd_export_blocked` (free users only), `edit_abandoned`.
- Per user `i` (`lumen_282506_{i:05d}`, from `data/lumen_dataset.json.gz`): edits in 7 days ≈
  `ai_edits_first_day × U(1.0, 1.6)` (40% background, 60% AI enhance), imports = `photos_imported` (≤30),
  exports ≈ 30–70% of edits, HD export attempts for 4+ edits. Paying = any non-refunded purchase.
- `random.Random(f"{run}:{i}")` and `uuid5` event ids: the same input always gives the same events, so a
  re-run is all duplicates.

## Contract touched
Client of `features`, `event-types`, `events`, `values:recompute`. Makefile: `offline-data` also copies
`lumen_dataset.json.gz`; new `demo-events`.

## How to test
```bash
make offline-data && make up        # api on :8000
make demo-events                    # second run: accepted 0, duplicates = events
```
Expected (measured): 1000 users, 25,226 events accepted in 9 s, `recompute` → 17 rules. Re-run: 0 accepted,
25,226 duplicates. `make test-docker` → 86 passed.

## Limits / not claimed
**Synthetic data.** The events are generated from the seed attributes, so a link between edits and revenue
is partly built in; the dashboard must label it. We checked the signal survives: users with 5+ edits in 7
days earn $12.09 vs $6.97 (1000 users; all 5000 seed users: $13.87 vs $6.42 by `ai_edits_first_day`).
The first **200** users alone invert it ($5.53 vs $9.20) — too small a sample, hence 1000 by default.

## Status
Done · All A tasks done. Next: support B (live mode), C (fast loop wiring), D (SDK switch).

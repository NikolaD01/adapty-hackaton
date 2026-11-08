# 13 — Wiring B into the running app

**Area:** C (as B's docs hand it over) · **Date:** 2026-11-08

## What
`main.py` calls `wire_brain` for the running app, so `insights:run` and `insights/latest` answer instead of `503 brain_not_configured`.

## How it works
`integrations/adapty/brain_wiring.py`:
1. `list_flows` runs `adapty flows list` (the configured app). No CLI or no login: the brain stays unconfigured, the API still starts.
2. `published_flows_from_listing` matches B's arm names to flow **names** (`FLOW_NAMES`) and keeps each flow's real `published` state.
   A missing flow is left out, never invented. No highlight feature is claimed for any flow.
3. `configure_demo_brain` registers one `BrainRuntime` for the demo app id `c6c7bdd1…` (what the data, scripts and web use) and for
   `ADAPTY_APP_ID` when it differs. Demo settings (explicit, synthetic data only): cutoff `2026-11-08T00:00:00Z`, outcome window
   **30 days** (`docs/brain/10-outcome-window.md`), identity map `lumen_282506_00000…04999`, the four `*_uses_7d` rules asserted as
   comparable with the seed outcomes. Without `data/lumen_dataset.json.gz` no live rule is asserted. Explanations are on only when an
   OpenAI key exists. The sink is the human-mode `ProposalService`.
4. B's trigger placement for the settings test is now `settings_upgrade` (the name in the Adapty app); it was `settings`.
5. Proposals created in one batch keep their order (one microsecond apart), which decides the shared `p_segment` key.

## Contract touched
`main.py` (shared), `domain/uplift.py` placement name (B). See `docs/contracts/CHANGES.md`.

## How to test
```bash
docker compose run --rm test
```
Expected: `525 passed`, `40 tasks, 0 problems`. Python 3.10 also: 525 passed.

## Limits / not claimed
- The settings are for the synthetic demo; another dataset needs its own cutoff, rules and identity map.
- Autopilot is not used by this sink: drafts from B wait for a human or for `POST /proposals`.

## Status
Done · Next: the real run, see chapter 14.

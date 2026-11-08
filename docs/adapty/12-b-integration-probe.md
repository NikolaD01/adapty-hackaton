# 12 — Probe with B's real insight run

**Area:** C · **Date:** 2026-11-08 · local database only, no Adapty writes (the Adapty key was blanked in the API container,
sync counted with a fake writer)

## What was run
B's offline `insights:run` (CSV, cutoff `2026-11-02T22:45:23Z`) with a `BrainRuntime` built by hand (flows of our Adapty app,
`ProposalService` as the sink), then A's `make demo-events` data (996 users, 17 rules).
Result: 8 drafts, 5 segments, 1 passed tier (`ai_edits_first_day`, cut points 0 and 2). Drafts store, list and carry
`segment_conditions` in the shape C reads.

## Findings
1. **B measures `ai_edits_first_day`, a historical column. No live rule has that key** (live rules are `ai_enhance_uses_7d` ...).
   So C's sync matches nobody and writes no `f_<feature>_tier`; an approved segment would exist in Adapty with no members.
   B documents this on purpose (a historical cut point must not be attached to a live rule that only looks similar).
   With the seed value `ai_edits_first_day` stored as a live value (simulation): tiers low 143 / mid 358 / high 500 over 1000
   users. Needs a decision by A and B: store the seed value as the baseline rule, or measure on a live rule (B's live mode needs
   150 users per side; there are 258 mature users).
2. Segments that differ only by a native filter (platform) share one `p_segment` key now (see 05).
3. B's trigger placement names come from its dataset (`main`, `onboarding`, `settings`); our Adapty app has `settings_upgrade`,
   so approving those drafts fails cleanly at `placement_read` (`placement_not_found`).
4. The demo data lives under `c6c7bdd1...` (default `ADAPTY_APP_ID` in `.env.example`), our Adapty app is `9ccde368...`: use one
   id for the whole demo.
5. Nothing wires `configure_brain` yet: `insights:run` answers `503 brain_not_configured`. B's docs hand this to C; it needs the
   app's verified flows and placement names, so it is a decision, not a one-liner.

## Not claimed
No draft was approved; nothing was written to Adapty. Counts are a simulation over synthetic data.

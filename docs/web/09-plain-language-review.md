# 09 — Plain-language proposal and insight review

**Area:** D (written by C on the team's request, D to ack) · **Branch/PR:** `web/plain-proposal-cards` · **Date:** 2026-11-08

## What
A proposal card now leads with a sentence a non-technical person can judge: who the group is, which paywall they
get, the expected net revenue per user with its likely range and sample size, and how the test splits the group.
The Insights page opens with one sentence per confirmed signal. Technical data is folded under "Technical details".

## Why
The card showed the segment hash as its title and B's analysis text with 15-decimal numbers, internal arm names
and two different hypotheses. Nobody outside the team could read it in the few seconds a demo gives.

## How it works
- `web/src/features/behavioral/plainLanguage.ts` (pure functions):
  - `audienceLabel` builds the title from the proposal's structured conditions only (`evidence.segment_conditions`,
    `adapty_filters`). Example: "Users who used AI enhance 1–3 times in 7 days · Android". Behavior comes first; the
    platform is a filter Adapty applies, so it goes last.
  - `fieldLabel` and `aboveThreshold` turn A's default rule keys (`<feature>_uses_7d`, `_uses_total`,
    `_days_active_7d`, `f_<feature>_tier`) into words. Unknown keys fall back to their words.
- `ProposalsPage.tsx`:
  - The card shows the expected effect, "likely between", and "Based on N users in a past randomized test"
    (`evidence.n_a + n_b`). Below 100 users it adds "A small sample: treat it as uncertain".
  - It also shows "Synthetic demo data" when `evidence.synthetic`, and "X% see the offer, Y% keep the current paywall".
  - `reason`, conditions, Adapty filters, ids, holdout, cooldown and the edit history are in a closed `<details>`.
  - The mode text explains Human and Autopilot in one sentence each.
- `InsightsPage.tsx`: `SignalSummary` sits above the ranking table: "Confirmed: users who used AI enhance at least
  once in 7 days bring 2.01× the net revenue of other users…", plus "Not confirmed: …".
  It also says that a signal shows who pays more, not why.

## Contract touched
None. It reads fields the API already returns. `Proposal.evidence` in `types/targeting.ts` now also types
`synthetic`, `n_a` and `n_b`.

## How to test
```bash
cd web && npx vitest --run
```
Expected: `49 passed`. `plainLanguage.test.ts` uses the real 60-day segments. `proposals.test.tsx` checks the
summary, the small-sample warning, and that the raw analysis text stays folded.

## Limits / not claimed
- The title wording knows A's default rule keys. AI-suggested keys are shown as their words, which is readable but
  plain.
- B's `reason` text is unchanged (raw numbers, two hypotheses). It is only moved under "Technical details".
- Events and Metrics screens are not changed in this chapter.

## Status
Done, waiting for D's ack · Next: Events and Metrics wording if time allows.

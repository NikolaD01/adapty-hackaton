# Role B — Brain (backend)

**Mission:** turn values into trustworthy groups and offers. The AI suggests *what to measure*;
statistics decides *what matters* and *what to show*. Two separate steps that must never merge:
**ranking finds WHO IS DIFFERENT, randomized arms decide WHAT TO SHOW THEM** (otherwise it is
propensity targeting = discount leakage).

## You own
`feature_signal/domain/{ranking,uplift}.py` · `feature_signal/services/{rule_suggest,insight}_service.py` ·
`feature_signal/api/v1/insights.py` (+ the `rules:suggest` route) · `feature_signal/integrations/llm/**` ·
`scripts/train_from_offline.py` · `tests/**/test_{ranking,uplift,insight,rule_suggest,llm}*.py` · `docs/brain/**`.

## Inputs / outputs
- In: `ValueStore.matrix()` (A) for live data; the offline dataset (`OFFLINE_DATA_DIR`, users.csv.gz +
  transactions.csv.gz) for training and the demo; `EventTypeRepo.list()` (A) for the LLM prompt.
- Out: `InsightRun` (contract) incl. `tiers` (written to `TierStore`) and `hypotheses`, and proposal
  drafts handed to C through `ProposalSink.create_many()`.

## Chapters
1. **Offline loader + outcome** — `scripts/train_from_offline.py` + an `OfflineDataset` adapter:
   per user `net_revenue_90d` = sum of non-refunded `price_usd` with `purchased_at < install_at + 90 d`,
   only users with a full 90-day window (≈12.5k). *Done when:* the script prints user count and mean
   outcome; unit test on a 5-row fixture.
2. **Ranking** (`domain/ranking.py`, pure) — for each numeric feature: best threshold by lift on a
   train split (70/30, fixed seed), report `lift`, `direction` (`up`/`down`), bootstrap 90% CI
   (≈400 resamples, ~15 lines), `holdout_lift` on the 30%, `passed = ci_low > 1 and holdout_lift > 1`
   (or the mirror for `down`). Minimum group size 150 per side.
   *Done when:* on the offline data it prints that `ai_edits_first_day` passes and `photos_imported`
   does not, with numbers (test with a synthetic matrix where one feature is pure noise → `passed=false`).
   **Tiers:** for each feature take its best passing value (usually `<f>_uses_7d`) and two cut points
   (`low_max`, `mid_max`) — start from the ranking threshold and the value tertiles, keep them only if
   net ARPU rises low < mid < high with non-overlapping CIs for low vs high; else `passed=false`. Max 10
   passed features (Adapty slot budget). Write them with `TierStore.put_many`.
   **Hypotheses:** rules whose values can't be joined to purchase outcomes (live-only events) are
   listed in `hypotheses`, never ranked or tiered.
3. **Segments** — combine passed features (as tiers) with Adapty-known fields (`subscription_state`,
   country tier, platform) into ≤5 `SegmentCandidate`s with size and `net_arpu_90d` ± CI. Stable
   `segment_key` slugs (they become `p_segment` values). In the draft, our part goes into `condition`
   (rule over our values), the Adapty-known part into `adapty_filters` (C maps the field names).
4. **Uplift** (`domain/uplift.py`, pure) — per segment, per randomized test in the dataset
   (`ab_test`/`flow` columns): difference in `net_revenue_90d` between arms with bootstrap CI.
   Recommend an arm only when the whole interval is on one side of zero. Known check: lifetime anchor
   +$14.40 for 5+ edits vs +$5.36 for 0. *Done when:* both numbers reproduce (±$0.5) in a test.
5. **Insights API** — `POST /insights:run {source}` and `GET /insights/latest`; `InsightService` builds
   proposal drafts (segment → `p_segment` condition + `adapty_filters`, better arm → `action.flow_id`
   (an already published flow, so autopilot can run it), `highlight_feature`, effect + CI, reason)
   and passes them to `ProposalSink`. A draft built on a hypothesis says so in `reason` and has no
   `expected_effect` CI from data (use 0 with a note). *Done when:* a run creates proposals visible at C's endpoint
   (use a fake sink in tests).
6. **LLM: rule suggestions + explanations** — `LLMProvider` port, OpenAI adapter
   (`LLM_PROVIDER=openai`, `LLM_MODEL` from env — verify the model id with `GET /v1/models` before the
   first call). Structured output (JSON schema) for `suggest_rules(catalog)` → `RuleSuggestion[]` and
   `explain()` → `{summary, hypothesis, confidence}`. Prompt in `integrations/llm/prompts.py`.
   The prompt gets features with their events and descriptions and the measure table from the contract;
   it suggests **composed** rules (ratio such as regenerate/generate, `sum`/`last` over numeric props,
   `where` such as `tokens_left <= 0`) on top of the default rules. Never suggest rules on free text.
   Fake provider for tests. *Done when:* `POST /rules:suggest` returns valid rules (schema-validated)
   with the fake; one manual real call recorded in `docs/brain/`.

## Tests you must have
Noise feature does not pass · threshold/lift on a hand-made matrix · bootstrap CI contains the true
diff on synthetic data · uplift sign and size on a fixture · 90-day outcome excludes refunds and
late purchases · LLM output that fails the schema is rejected (fallback = no suggestion, not a crash).

## Pitfalls
- `ai_limit_reached` $31.18 vs onboarding $6.14 is selection (5.42 vs 3.34 edits) → never present as causal.
- Placement assignment is not randomized; only `ab_test` arms are.
- Don't let the LLM pick thresholds, tiers or rank: it may only propose rule definitions and write text.
- A ratio like regenerate/generate can mean "unhappy" or "engaged" — measurement decides, not the label.
- Weekly wins the 90-day window but has 2.7× refunds — report refunds next to every uplift.

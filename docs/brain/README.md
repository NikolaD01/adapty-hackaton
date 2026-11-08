# Brain (B)

B1–B8 are implemented on `feat/segment-b-brain`. Statistics selects measured groups and randomized
winners; the model suggests measurements and chooses constrained explanatory hypotheses.

| Chapter | Implementation |
|---|---|
| [01 — Offline outcomes](01-offline-outcomes.md) | Mature users, fixed 90 days, refunds, CSV input |
| [02 — Ranking and tiers](02-ranking-and-tiers.md) | Train/holdout, bootstrap intervals, measured tiers |
| [03 — Segments](03-segments.md) | Stable keys, raw predicates, native filters, five-candidate cap |
| [04 — Uplift](04-uplift.md) | Randomized arms, fixed window, refund diagnostics |
| [05 — Insights API](05-insights-api.md) | Real A repositories, C sink handoff, runtime configuration |
| [06 — Suggestions](06-rule-suggestions.md) | Structured rules, semantic validation, live model verification |
| [07 — Explanations](07-explanations.md) | Numerical facts preserved, constrained tentative text |
| [08 — Live insights](08-live-insights.md) | Verified identity/measurement joins, explicit offline fallback |
| [09 — Seed JSON outcomes](09-seed-outcomes.md) | A's relative-clock JSON, first 1000 seed users by default |

Reproduce the offline analysis (the CSV cutoff below is an explicit maximum-install-time assumption):

```bash
python scripts/train_from_offline.py --data-dir data/offline --as-of 2026-11-02T22:45:23Z --analysis
```

Reproduce seed purchase outcomes (the timestamp is an arithmetic anchor for relative dataset time):

```bash
python scripts/train_from_offline.py --seed-json data/lumen_dataset.json.gz --as-of 2026-11-08T00:00:00Z
```

Verified CSV result: 12,452 mature users, mean $9.588070; first-day edits pass and imported photos fail.
Verified first-1000 JSON result: 258 mature users, mean $9.483798. A's actual demo returned 17 live rankings
with no passing tiers after the maturity/minimum-size checks. Both sources are synthetic.

The existing fixed-90-day metric is retained by the developer's decision; older +$14.40/+ $5.36 targets
used a different observation basis. See chapter 04 for the corrected estimates and intervals.

`POST /rules:suggest` uses real catalog repositories and configured OpenAI credentials. Verified model:
`gpt-6-luna`; Luna 6.1 was absent from the account's model list. Numerical insight routes require
`configure_brain(app, app_id, BrainRuntime(...))` with an explicit cutoff, C's real proposal sink and
app-specific verified flows. Chapter 05 describes the handoff. No production fake is installed.

The actual B→C proposal/storage/membership contract was exercised against C's remote source with no
external calls. Production activation and deployment are outside B's branch. The original
[execution checklist](2026-11-08-phase-b-implementation-plan.md) and [A's handoff](../ingest/README.md#for-b-brain)
remain linked for integration review.

# AI log

How we used AI, and where it was wrong. Every entry: what the AI claimed → how we checked → what
was true. Newest first. Append only.

| Date | Area | AI claimed | How we checked | Correction |
|---|---|---|---|---|
| 2026-11-07 | brain | Ranking could choose both the group and the offer from one measurement | Human review of the plan | Split into two steps: ranking finds the group, randomized A/B arms choose the offer (otherwise discount leakage) |
| 2026-11-07 | adapty | Attribute write is a POST with an object body | Real call on a test profile | PATCH with a list body; an object returns 400 "value is not a valid list" |
| 2026-11-07 | adapty | A placement can serve "nothing" to an audience | Four placement variants tried on a test placement | Refused: a placement needs ≥1 audience and a default audience; control arm = default flow |
| 2026-11-07 | brain | Annual trial beats weekly once revenue matures | Re-computed with a fixed 90-day window (12,452 users) | Weekly still wins net in 90 days (+$4.33, 90% CI [+3.56, +5.05]) but with 2.7× refunds |
| 2026-11-07 | brain | Contextual paywall earns 4× more | Compared first-day edits by placement | Partly selection: 5.4 edits vs 2.8–3.3; effect survives control but the raw number was inflated |
| 2026-11-07 | research | Adapty has no benchmark data | Read the CSV files in the skills repo | It has `market-grid.csv` with medians and percentiles |
| 2026-11-07 | research | "Revenue audit" is a new idea | Read Adapty's skills | `growth-advisor` already does it |

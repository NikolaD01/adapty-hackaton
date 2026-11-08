# Documentation index

Start with [plan.md](plan.md).

## Product and decisions
- [diagrams/](diagrams/README.md) — Mermaid diagrams: system, flow, ingest sequence, proposal lifecycle, data model.
- [plan.md](plan.md) — what we build, why, how we measure, what we don't claim, demo script.
- [STATUS.md](STATUS.md) — one row per area, updated at every chapter end.
- [demo.md](demo.md) — the 3-minute demo script, numbers we say, backup plan (C's minute in detail: [adapty/11-demo-script.md](adapty/11-demo-script.md)).

## Contract (shared, change only through `contract-change`)
- [contracts/api.md](contracts/api.md) — every endpoint and schema, Adapty attribute keys.
- [contracts/ports.md](contracts/ports.md) — ports and domain models between areas.
- [contracts/CHANGES.md](contracts/CHANGES.md) — log of contract changes.

## Team
- [team/ONBOARDING.md](team/ONBOARDING.md) — 10-minute setup for people.
- Role briefs: [A — Ingest & Rules](team/A-ingest-rules.md) · [B — Brain](team/B-brain.md) ·
  [C — Adapty & Proposals](team/C-adapty-proposals.md) · [D — Dashboard & Demo](team/D-dashboard.md).
- [tasks/README.md](tasks/README.md) — task graph (`make board ROLE=X`, `tools/tasks.py inbox --role X`).
- [templates/chapter.md](templates/chapter.md) — template for chapter docs.

## Chapter docs by area
| Area | Index | Chapters |
|---|---|---|
| A — Ingest & Rules | [ingest/README.md](ingest/README.md) (what is ready for B, C, D) | [01 tables](ingest/01-tables-migration.md) · [02 features + catalog](ingest/02-features-catalog.md) · [03 ingest](ingest/03-idempotent-ingest.md) · [04 timeline](ingest/04-user-timeline.md) · [05 rules engine](ingest/05-rules-engine.md) · [06 values + profile](ingest/06-values-profile.md) · [07 SDK](ingest/07-sdk.md) · [08 demo events](ingest/08-demo-events.md) · [09 Adapty webhook](ingest/09-adapty-webhook.md) |
| B — Brain | [brain/README.md](brain/README.md) | [01 outcomes](brain/01-offline-outcomes.md) · [02 ranking](brain/02-ranking-and-tiers.md) · [03 segments](brain/03-segments.md) · [04 uplift](brain/04-uplift.md) · [05 API](brain/05-insights-api.md) · [06 suggestions](brain/06-rule-suggestions.md) · [07 explanations](brain/07-explanations.md) · [08 live](brain/08-live-insights.md) · [09 seed JSON](brain/09-seed-outcomes.md) |
| C — Adapty & Proposals | [adapty/README.md](adapty/README.md) | [00 plan](adapty/00-plan.md) · [01 profile client](adapty/01-profile-client.md) · [02 CLI](adapty/02-cli.md) · [03 lookup](adapty/03-lookup.md) · [04 proposals](adapty/04-proposals-store.md) · [05 membership sync](adapty/05-membership-sync.md) · [06 activation](adapty/06-activation.md) · [07 decision log](adapty/07-decision-log.md) · [08 autopilot](adapty/08-autopilot.md) · [09 paywall draft](adapty/09-paywall-draft.md) · [10 end-to-end probe](adapty/10-end-to-end-probe.md) · [11 demo, part C](adapty/11-demo-script.md) |
| D — Dashboard & Demo | [web/README.md](web/README.md) | [01 web scaffold](web/01-web-scaffold.md) · [02 — Proposal review and controls](web/02-proposals.md) · [03 — Insights and Metrics](web/03-insights-metrics.md) · [04 — Lumen demo access and tracking](web/04-lumen-tracking.md) · [05 — Event catalog and activity](web/05-event-catalog.md) · [06 — Decisions and flow lookup](web/06-decisions-lookup.md) · [07 — Live API verification](web/07-live-verification.md) |
Each area adds its chapter to this table in the same PR as the chapter doc.

## Elsewhere in the repo
[../README.md](../README.md) · [../CLAUDE.md](../CLAUDE.md) (rules for agents) · [../AI_LOG.md](../AI_LOG.md) ·
[../sdk/js/README.md](../sdk/js/README.md)

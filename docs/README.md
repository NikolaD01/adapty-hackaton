# Documentation index

Start with the [diagram](https://claude.ai/artifact/X9YbYnKEExYeSZjmAC733h) and [plan.md](plan.md).

## Product and decisions
- [plan.md](plan.md) — what we build, why, how we measure, what we don't claim, demo script.
- [STATUS.md](STATUS.md) — one row per area, updated at every chapter end.

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
| A — Ingest & Rules | [ingest/README.md](ingest/README.md) (what is ready for B, C, D) | [01 tables](ingest/01-tables-migration.md) · [02 features + catalog](ingest/02-features-catalog.md) · [03 ingest](ingest/03-idempotent-ingest.md) · [04 timeline](ingest/04-user-timeline.md) · [05 rules engine](ingest/05-rules-engine.md) · [06 values + profile](ingest/06-values-profile.md) · [07 SDK](ingest/07-sdk.md) · [08 demo events](ingest/08-demo-events.md) |
| B — Brain | [brain/README.md](brain/README.md) | — |
| C — Adapty & Proposals | [adapty/README.md](adapty/README.md) | — |
| D — Dashboard & Demo | [web/README.md](web/README.md) | [01 web scaffold](web/01-web-scaffold.md) |

Each area adds its chapter to this table in the same PR as the chapter doc.

## Elsewhere in the repo
[../README.md](../README.md) · [../CLAUDE.md](../CLAUDE.md) (rules for agents) · [../AI_LOG.md](../AI_LOG.md) ·
[../sdk/js/README.md](../sdk/js/README.md)

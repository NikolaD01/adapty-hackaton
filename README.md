# Feature Signal for Adapty

[![ci](https://github.com/NikolaD01/adapty-hackaton/actions/workflows/ci.yml/badge.svg)](https://github.com/NikolaD01/adapty-hackaton/actions/workflows/ci.yml)

An add-on for Adapty that learns from what users **do** in the app which group should see which offer.
The app sends behavior events through a tiny SDK; we keep the history, compute values per feature,
measure which values really separate buyers, and write only the decision into Adapty
(`p_segment` + `f_<feature>_tier`, at most 11 of 30 attributes). Adapty's own segments, audiences and
A/B tests then serve and measure the offer. Human mode by default; autopilot within limits; publishing a
paywall is always a human click.

**Plan:** [docs/plan.md](docs/plan.md) · **Diagrams:** [docs/diagrams](docs/diagrams/README.md) · **All docs:** [docs/README.md](docs/README.md)

## How it works
Full picture: [flow diagram](docs/diagrams/flow.md) · [system](docs/diagrams/system.md).

1. **App** — `track("ai_enhance", { edits_left: 0 })` via `feature-signal-sdk` (buffered, retry-safe).
2. **Catalog** — features (groups of events, with the plans that include them) and event types.
3. **History** — one row per event (who, what, phone time, arrival time); a repeated `event_id` counts once.
4. **Feature profile** — default values per feature (uses, uses in 7 days, active days, used X) plus
   composed rules (ratio, sum, last, `where tokens_left <= 0`), refreshed after every event.
5. **AI suggests, measurement checks** — only values that hold on unseen users become tiers.
6. **Adapty attributes** — `f_<feature>_tier` = low/mid/high for measured features, `p_segment` for the approved group.
7. **Segment** — `p_segment` AND Adapty's own filters (e.g. no subscription).
8. **Paywall + A/B test** — control keeps the current paywall; we compare net revenue in 90 days.

## What works today
| Part | Owner | State |
|---|---|---|
| Tables, migrations, features + event catalog, idempotent ingest, timeline, rules engine (all measures), values, feature profile, TierStore | A | ✅ on `main` ([docs/ingest](docs/ingest/README.md)) |
| JS SDK `sdk/js` | A | ✅ on `main` ([chapter 07](docs/ingest/07-sdk.md)) |
| Synthetic demo events for 1000 seed users | A | ✅ `make demo-events` ([chapter 08](docs/ingest/08-demo-events.md)) |
| Adapty webhook: real purchases and refunds as events, live net revenue per user | A | ✅ `POST /adapty-webhook` ([chapter 09](docs/ingest/09-adapty-webhook.md)) |
| Dashboard scaffold (`web/`) | D | ✅ scaffold on mocks ([docs/web](docs/web/01-web-scaffold.md)) |
| Ranking, tiers, uplift, insights, LLM suggestions | B | Implemented on this branch; insight runs require app-scoped runtime configuration ([docs/brain](docs/brain/README.md)) |
| Adapty attributes, segments, A/B, proposals, membership sync, lookup, paywall draft | C | ⏳ routes return `501 not_implemented` |

Live status per area: [docs/STATUS.md](docs/STATUS.md) · task graph: `make board`.

## Quick start
One command for a demo: `make demo` (or `make demo-reset` for a clean database) — then follow
[docs/demo.md](docs/demo.md). Step by step:
```bash
cp .env.example .env              # fill ADAPTY_SECRET_KEY (C) / OPENAI_API_KEY (B) if you need them
make up                           # API with the Adapty CLI in Docker → http://localhost:8000/docs (runs migrations)
make offline-data                 # seed datasets into data/ (offline CSVs + lumen_dataset.json.gz)
make demo-events                  # 1000 synthetic seed users, ~25k events, values recomputed
curl -s "localhost:8000/v1/apps/c6c7bdd1-1010-4343-8b29-837a77793cab/users/lumen_282506_00007/features"
```
Tests: `make test-docker` (lint, 340+ backend tests, task graph — same as CI) · SDK: `cd sdk/js && npm install && npm test -- --run` ·
Web: `cd web && npm install && npm run dev` → http://localhost:5173.

## Repository map
```
feature_signal/   FastAPI backend — api/v1 (routes) · schemas · domain (pure rules/ranking/uplift) ·
                  repositories · services · integrations (adapty, llm) · db (tables, migrations)
sdk/js/           feature-signal-sdk (TypeScript, zero dependencies)
web/              dashboard + demo app (React, Vite, MSW mocks)
scripts/          load_demo_events.py, offline training
tests/            unit · service · integration (shared fixtures in tests/integration/conftest.py)
docs/             plan, contract, role briefs, chapter docs, task graph — index in docs/README.md
tools/tasks.py    task graph: board, impact, change notices
```

## Team workflow
Four developers, four agents, in parallel. Rules for agents: [CLAUDE.md](CLAUDE.md). People:
[docs/team/ONBOARDING.md](docs/team/ONBOARDING.md). One chapter = one branch `<area>/<name>` = one PR,
squash-merged when CI is green. Shared files change through the `contract-change` skill. AI use is
documented in [AI_LOG.md](AI_LOG.md), never in commit messages.

## What we don't claim
The Lumen data is synthetic (realistic shape, relationships built in); demo events are generated and
marked `synthetic`. Adapty serves per segment, not per user. Timing effects in the data (limit-reached
paywall) are a hint, not causal.

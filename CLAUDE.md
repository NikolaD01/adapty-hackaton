# CLAUDE.md — Feature Signal for Adapty

Read this whole file before doing anything. Then read your role brief (below). Four developers and
four agents work in this repo **at the same time** until code freeze (Sunday 8 Nov, see the timeline in §11). Speed matters,
but `main` must always run.

## 1. What we build (one paragraph)
An add-on for Adapty that learns from what users *do* inside the app which group should see which
offer. The developer groups events into **features** and the app sends them (with small numeric props
like `tokens_left`) through our tiny SDK. We store the history, keep a profile per user and feature
(default values + composed values the AI suggests), measure which values really separate buyers,
turn passed ones into `low/mid/high` tiers, find groups that differ, pick the offer for each group from
**randomized** A/B arms, and write only `p_segment` + `f_<feature>_tier` into Adapty (≤11 of 30 slots).
A fast loop re-checks a user after every event and writes only changed attributes. Adapty's own machinery then serves a different paywall to that segment and an
A/B test with a holdout measures net revenue. Two modes: **human** (default: a person approves,
edits or rejects every proposal) and **autopilot** (bounded; publishing a flow is always human).
We do **not** build a paywall editor, billing SDK or analytics — Adapty has those.

Full plan: `docs/plan.md`. API contract: `docs/contracts/api.md`. Ports and models: `docs/contracts/ports.md`.

## 2. Find your role
Your role is in `CLAUDE.local.md` (gitignored, one line: `My role: A|B|C|D`). If it is missing, ask
the developer which role they have, then create it. Then read your brief:

| Role | Brief | Owns |
|---|---|---|
| **A — Ingest & Rules** (backend) | `docs/team/A-ingest-rules.md` | SDK, event catalog, ingest, rules engine, values, DB migrations |
| **B — Brain** (backend) | `docs/team/B-brain.md` | rule suggestions (LLM), ranking, uplift, insights, offline training |
| **C — Adapty & Proposals** (backend) | `docs/team/C-adapty-proposals.md` | Adapty clients, proposals, modes, decision log, lookup, paywall draft |
| **D — Dashboard & Demo** (frontend) | `docs/team/D-dashboard.md` | `web/`: our dashboard page + demo app |

**Stay in your lane.** Edit only files your area owns (see §6). If you need something from another
area, use its port with a fake in your tests and keep going; never wait, never edit their files.

## 3. Stack (fixed — do not add frameworks without a contract change)
- Backend: Python 3.10+, FastAPI + uvicorn, pydantic v2 + pydantic-settings, SQLAlchemy 2.0 async +
  aiosqlite, Alembic, pandas, scikit-learn, httpx, openai SDK (LLM behind a port), pytest + pytest-asyncio, ruff.
- Frontend: React 18 + Vite + TypeScript, Tailwind, TanStack Query, MSW (mocks from the contract), Vitest + Testing Library.
- SDK: TypeScript, zero runtime deps, in `sdk/js/`.
- Adapty: Server-side API (httpx) + Adapty CLI 0.18 (subprocess). DB: SQLite file `data/app.db`.

## 4. Architecture rules (they are what makes parallel work possible)
Ports and adapters. Each layer knows one thing.
```
feature_signal/
  main.py            create_app(), mounts routers
  core/              config.py (Settings — the ONLY place secrets live), errors.py
  api/v1/            thin routes: parse → call service → return. No logic, no SQL.
  schemas/           pydantic models = docs/contracts/api.md
  domain/            models.py, ports.py, rules.py, ranking.py, uplift.py — pure functions, NO I/O
  repositories/      SQLAlchemy; knows tables, not HTTP
  services/          order of work; depends on ports passed in the constructor
  integrations/      adapty/ (profile_client.py, cli.py), llm/ (provider, prompts)
  db/                session.py, tables.py, migrations/
tests/  unit/ (domain, no I/O)  service/ (fake ports, no I/O)  integration/ (sqlite in memory)
scripts/            train_from_offline.py, seed helpers
sdk/js/             track() SDK
web/                dashboard + demo app
```
Five hard rules: no service imports fastapi · no repository knows HTTP · `domain/` imports nothing
from `integrations/`, `repositories/` or `api/` · secrets only in `core/config.py` Settings · anything
external comes in through a port in the constructor. Consequence we rely on in the pitch:
**statistics decides, the LLM only explains** — `domain/ranking.py` physically cannot call a model.
The LLM touches exactly two services: `rule_suggest_service` (B) and `paywall_service` (C).

## 5. Verified facts (do not re-derive, do not contradict)
- Adapty attribute write: `PATCH https://api.adapty.io/api/v2/server-side-api/profile/`, headers
  `Authorization: Api-Key <secret>` + `adapty-customer-user-id: <id>`, body is a **list**:
  `{"custom_attributes":[{"key":"p_segment","value":"power_editor"}]}` (an object → 400). PATCH merges,
  `value: null` deletes one key. Limits: 30 attributes/profile, key ≤30 chars, value ≤50 chars.
- Change reaches the segment in **0.6 s** (segment_hash changes). The SDK cache serves the old flow until
  the profile refreshes → demo uses the server-side lookup.
- Segment filter on a custom attribute: `attributes__<key>@string` (IN, NOT IN, IS NULL, IS NOT NULL) or
  `@float` (comparisons). A bare key is refused.
- A placement must keep ≥1 audience **and** a default audience; "show nothing" does not exist → the
  control arm is the existing default flow. `placements update` needs `--developer-id` and the full
  `--audiences` list (read with `placements get` first).
- Flows: `flows create` → `flows config update --config-file` → `flows publish` (async: `publishing`
  → `published`). An unpublished flow on an audience → 400. A/B: `ab-tests create` (draft) → `start`.
- Paywall views per user are not available through the CLI (S3 export only); the profile has no field
  for the A/B arm → we read Adapty's per-arm result.
- Lumen app id `c6c7bdd1-1010-4343-8b29-837a77793cab`, seed run `282506` (users `lumen_282506_NNNNN`),
  flows: default main `50562f3c-…`, lifetime `4d8837b5-…`. Offline dataset: `data/offline/` of
  `kpotehin/adapty-seed-data-hack` (50,000 users; columns incl. `ai_edits_first_day`, `placement`,
  `flow`, `ab_test`). Key numbers: `ai_edits_first_day` ARPU $3.73→$16.57, `photos_imported` flat
  $8.73–$9.55; lifetime anchor +$14.40 for 5+ edits vs +$5.36 for 0 (randomized); weekly refund 6.9%.
- Metric: **net revenue in 90 days** (refunds subtracted, same window for both arms). Never conversion alone.
- Adapty CLI 0.18 has **no delete** for segments or placements (only create/get/list/update); deleting is
  manual in the dashboard. So: create segments only on approve, idempotent by title `[fs] <segment_key>`
  (look up with `segments list` first, then `update`); never create throwaway segments in tests or loops;
  "undo" = remove the audience from the placement and null our `p_segment` / `f_*_tier` attributes. Tests use fakes only.
- Feature keys ≤22 chars (they become `f_<key>_tier`, Adapty key max 30). Event props carry numbers and
  short labels, never free text (prompts stay in the app). Quotas come from the app as state (`tokens_left`).
- Time of day is not collected: Adapty serves per segment, not per hour.
- LLM: OpenAI (key in `.env`). The model id in `.env.example` is a placeholder until B verifies it with
  `GET /v1/models`; never hard-code a model name outside `core/config.py`.

## 6. Ownership (who may edit what)
| Path | Owner | Others |
|---|---|---|
| `sdk/js/**`, `api/v1/{events,catalog,rules,values}.py`, `repositories/{features,event_types,events,rules,values,tiers}.py`, `services/{catalog,ingest,rule,value}_service.py`, `domain/rules.py`, `db/**` (tables + migrations), `alembic.ini` | A | read only |
| `domain/{ranking,uplift}.py`, `services/{rule_suggest,insight}_service.py`, `api/v1/insights.py`, `integrations/llm/**`, `scripts/train_from_offline.py` | B | read only |
| `integrations/adapty/**`, `services/{proposal,activation,paywall,lookup,membership}_service.py`, `api/v1/{proposals,settings,decisions,lookup,membership}.py`, `repositories/{proposals,decisions}.py` | C | read only |
| `web/**` | D | read only |
| **Shared:** `schemas/**`, `domain/models.py`, `domain/ports.py`, `docs/contracts/**`, `core/**`, `main.py`, `api/v1/router.py`, `pyproject.toml`, `Makefile`, `.claude/**`, `CLAUDE.md`, `tools/**`, `.github/**`, `docs/tasks/shared.json` | everyone, **only via the `contract-change` skill** (small PR, one teammate acks) | |
| `docs/<your-area>/**`, `AI_LOG.md` (edit sections in place), `docs/STATUS.md` (your row only), `docs/tasks/<ROLE>.json` (your file only) | you | |
| `docs/tasks/changes/*.json` (change notices) | anyone adds a new file | never edit others' notices |
New tables: tell A (A owns migrations); C adds `proposals`/`decisions` table definitions to `db/tables.py`
through A or via a contract-change PR.

## 7. Git workflow
- `main` is protected by habit: always green, always runnable. Nobody commits to `main` directly.
- **Branch:** `<area>/<short-kebab>` — areas: `ingest`, `rules`, `brain`, `adapty`, `web`, `sdk`, `docs`, `contracts`, `chore`.
  Examples: `ingest/idempotent-batch`, `brain/ranking-holdout`, `adapty/segment-activation`, `web/proposal-cards`.
  Short-lived: open, finish one chapter, merge. Target ≤ 2 hours per branch.
- **Commits:** Conventional Commits, English, imperative, ≤72 chars subject:
  `feat(ingest): add idempotent event batch endpoint` · `test(brain): cover bootstrap interval` ·
  `fix(adapty): send custom attributes as a list` · `docs(web): describe proposal card states`.
  Types: `feat fix test docs refactor chore perf`. Scope = area. Optional body: *why*, wrapped at 72.
  Each commit compiles and keeps your area's tests green. Commit in small logical pieces
  (code + its test together), not one giant commit at the end.
- **No AI attribution anywhere:** no `Co-Authored-By`, no "Generated with…", no model names, no AI
  mentions in commit messages, PR titles or PR bodies. (Project settings already disable the trailer.)
  AI usage is documented only in `AI_LOG.md`.
- **Sync often:** `git fetch origin && git rebase origin/main` before every push and at least hourly.
  Never `push --force` to `main`; on your own branch only `--force-with-lease`.
- **Merge:** push branch → PR to `main` (title = conventional commit) → CI/`make test` green →
  **squash merge** → delete branch. Self-merge is fine; a PR touching shared files (§6) needs one
  teammate's ack. Use the `chapter-done` skill — it does all of this.
- Conflicts: resolve in *your* branch; if the conflict is in another area's file, take theirs and
  re-apply your change through your own files.

## 8. Tests (required for every feature)
- Backend: `make test` (pytest). Domain → unit tests with plain numbers; services → fake ports;
  repositories → SQLite in memory. **No test touches the network** (Adapty and the LLM are faked;
  real calls are done by hand, once, for the demo). Names: `tests/<level>/test_<module>.py`,
  `test_<behavior>_<condition>`.
- Must-have tests (jury criterion): ranking is not noise (holdout + interval), attribute payload shape
  (list body, key/value limits), ingest idempotency (same `event_id` twice → counted once).
- Frontend: `npm test` in `web/` (Vitest + Testing Library), MSW handlers built from the contract.
- Never merge with red tests. If a test of another area breaks because of you, fix your change.

## 9. Documentation (uniform, so it can be merged into one README)
- Per chapter: `docs/<area>/<NN>-<slug>.md` from `docs/templates/chapter.md` (What · Why · How it works
  · Contract touched · How to test · Limits / not claimed · Status). English, short sentences, numbers
  with units, no marketing words.
- `docs/STATUS.md`: one row per area — update your row at every chapter end.
- Indexes: `docs/README.md` (all docs, one row per area) and `docs/<area>/README.md` list every chapter;
  the root `README.md` "What works today" table says what is real. Update them in the chapter's PR.
- `AI_LOG.md` (jury criterion, **½–1 page**, fixed sections): tools used and for what · setup (rules files,
  agents, MCP, subagents) · 2–3 prompts that worked well · one thing AI got wrong and how it was caught ·
  what we'd never delegate to AI. Edit the sections in place (replace a weaker example with a better one);
  never turn it into a diary.
- `README.md` is assembled in Phase 6 from the chapter docs; don't write prose there before that.

## 10. Skills in this repo
- `chapter-done` — run when a chapter (feature) is finished: scope check, missing tests, run tests,
  write the chapter doc, update STATUS/AI_LOG, commit in pieces, rebase, push, open PR, squash-merge when green.
- `sync-main` — rebase your branch on `origin/main`, rerun tests, push.
- `contract-change` — the only way to change shared files (§6).
Adapty's own skills are enabled too (`adapty-skills@adapty`: audiences, ab-tests, flow-generator, …):
use them as reference for CLI usage.

## 10a. Task graph (`docs/tasks/`, details in `docs/tasks/README.md`)
Every task of every role lives in `docs/tasks/<ROLE>.json`: steps, `depends_on` (`hard` = wait,
`contract` = start now on fakes, re-check later), `produces`/`consumes`, `done_when`. Use `tools/tasks.py`:
- **Start of a session:** `board --role <me>` (pick a `ready` task, `set <id> doing`) and `inbox --role <me>`.
- **Before changing an output others use** (schema, port, table, value meaning): `impact <id> --depth 1`.
- **When an output changed or you found it wrong** — yours or someone else's: `flag <id> --by <me> --reason "…"`,
  commit the notice, and tell the developer which roles to ping. Never edit another role's task file.
- **On a REVIEW NOW hit in your inbox:** re-run your tests against the change; if something must change, `set <id>
  needs-review` and fix it in the next chapter; then `ack --role <me>`.
- New task or dependency discovered → add it to your file in the same PR; `check` is a unit test.

## 11. Phases and team sync points
Phase 0 setup (done) · 1 ingest (A) · 2 brain (B) · 3 Adapty loop (C — riskiest, do it early while
mentors are here) · 4 demo client + dashboard (D) · 5 paywall draft (C) · 6 README, AI_LOG, demo video
(all) · 7 rehearsal + submit. Sync points (10 min, everyone): **S1** after A's ingest + D's mocks run;
**S2** first end-to-end: event → value → insight → proposal → approve → segment in Adapty; **S3** demo
dry run. What we cut if late, in order: our MCP server, dashboard polish, generated paywall copy.
We never cut Phase 3.

Timeline (code freeze **8 Nov, morning**; exact hour from the organizers — update here when known):
S1 by 23:30 on 7 Nov · S2 (end-to-end on Lumen) by 04:00 · demo video recorded by 07:30 · S3 rehearsal
08:00 · submit right after. If S2 is not reached by 04:00, cut in the listed order and move C8 out.

## 12. Working style for agents
- Deliver fast in small verified steps. Prefer the simplest thing that satisfies the contract.
- Before saying "done": tests pass, `ruff check` clean, the chapter doc exists.
- Do not invent Adapty behavior: check §5, the Adapty skills, or ask the developer.
- Never print or commit secrets; `.env` is gitignored, `.env.example` lists names only.
- **Language rule:** everything written into the repo is English — code, comments, docstrings, docs,
  READMEs, commit messages, PR titles and bodies, test names, UI text. Talk to the developer in Serbian.
  If you find non-English text in a file you own, translate it in the same chapter.

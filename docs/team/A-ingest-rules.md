# Role A — Ingest & Rules (backend)

**Mission:** events go in reliably, values come out. You own the data plane: SDK → features and event
catalog → event history → rules → per-user values and feature profiles. Everyone else reads what you produce.
A **feature** is a group of events the developer defines (as wide or narrow as they want); each feature
gets default values automatically, the AI adds composed ones.

## You own
`sdk/js/**` · `feature_signal/api/v1/{events,catalog,rules,values}.py` ·
`feature_signal/repositories/{event_types,events,rules,values}.py` ·
`feature_signal/services/{ingest,rule,value}_service.py` · `feature_signal/domain/rules.py` ·
`feature_signal/db/**` (all tables and Alembic migrations, including tables others need) ·
`tests/**/test_{ingest,events,catalog,rules,values}*.py` · `docs/ingest/**`.

## Inputs / outputs
- In: HTTP from the SDK and dashboard (contract: `docs/contracts/api.md`, owner A rows).
- Out: `ValueStore.matrix(app_id)` → `FeatureMatrix` (one row per `customer_user_id`, one column per
  rule key) — B ranks it, C turns it into `f_<feature>_tier` and `p_segment`. Keep this port stable.
- Out: `GET /users/{id}/features` (feature profile for D) and `TierStore` (table you own; B writes, C reads).
- You call: `MembershipSync.sync_users(app_id, ids)` (C) after every ingest batch commits — fire and
  forget (background task), never inside the ingest transaction; a failure there must not fail ingest.

## Chapters (in order; each ends with the `chapter-done` skill)
1. **Tables + migration** — `features(app_id, key, name, description, plans JSON, created_at)` PK `(app_id, key)`,
   `event_types(app_id, action_id PK int, key, name, description, created_at)`,
   `event_type_features(app_id, action_id, feature_key)` (an event may be in several features),
   `feature_tiers(app_id, feature, rule_key, low_max, mid_max, passed, updated_at)` PK `(app_id, feature)`,
   `events(event_id PK uuid, app_id, customer_user_id, action_id, occurred_at, received_at, props JSON, decision_id NULL)`
   with one index `(app_id, customer_user_id, occurred_at)`, `user_action_counts(app_id, customer_user_id,
   action_id, n, last_ts)` PK `(app_id, customer_user_id, action_id)`, `rules(...)`, `user_values(app_id,
   customer_user_id, rule_key, value, computed_at)` PK `(app_id, customer_user_id, rule_key)`; `rules` has a
   nullable `feature` column and `source` ∈ human/ai/default. Also add
   C's `proposals` and `decisions` tables (columns from the Proposal/Decision schemas, JSON columns for
   nested parts). Integer `action_id`, never the string key, in `events`.
   *Done when:* `alembic upgrade head` creates everything; integration test inserts and reads one row per table.
2. **Features + catalog** — `POST/GET /features` (upsert by key; on create, insert the default rules:
   `<f>_uses_total`, `<f>_uses_7d`, `<f>_days_active_7d`, `<f>_used_<event>` per event — and add the
   `used_` rule when an event joins the feature later) and `POST/GET /event-types` with `features: [...]`
   (unknown feature key → 422). *Done when:* creating `ai_generate` + 3 events yields 6 default rules;
   re-registering a key updates it (200); tests cover both.
3. **Idempotent ingest** — `POST /events`. In ONE transaction: insert into `events` with
   `ON CONFLICT(event_id) DO NOTHING`; increment `user_action_counts` **only for rows actually inserted**
   (use the insert's rowcount / RETURNING). Unknown keys → `unknown_keys`. Max 500 per batch.
   `props` validation is in the schema (numbers stay numbers, strings ≤100, ≤20 props). After commit,
   schedule `MembershipSync.sync_users(app_id, <users in the batch>)` as a background task (fake in tests).
   *Done when:* curl sends an event, it is in the DB; same `event_id` twice → `duplicates: 1` and the counter unchanged (test).
4. **SDK** — `sdk/js/src/index.ts`: `init({ baseUrl, appId, customerUserId })`, `registerEventType(...)`,
   `track(key, props?)` (generates `event_id` with `crypto.randomUUID()`, sets `occurred_at`, buffers,
   flushes every 2 s or 20 events, retries with the same ids). ~50 lines, no deps. Build with `tsc`.
   Vitest unit test with a fake fetch. Keep `sdk/js/src/index.ts` the single entry, zero runtime dependencies, browser APIs only (`fetch`, `crypto.randomUUID`, `setTimeout`).
   *Done when:* D can `import { init, track } from 'feature-signal-sdk'` (Vite alias, see D brief) and events arrive.
5. **Rules engine** — `domain/rules.py`: `apply(rule: RuleDefinition, events: list[Event], now) -> float`
   for `count`, `distinct` (by `props[distinct_prop]`), `exists`, `days_active`, `ratio`
   (count / count of `denominator_event_keys`, 0 when the denominator is 0), `sum`/`max`/`min`/`last`
   over the numeric `props[value_prop]` (`last` = latest `occurred_at`; events missing the prop are
   skipped; no events → 0), optional `where` filter applied first, `window_days` on `occurred_at`
   (never `received_at`). Pure function. `POST/GET /rules`.
   *Done when:* unit tests for each measure, `where`, ratio with zero denominator and the window edge
   (event exactly at the boundary) pass.
6. **Values** — `POST /values:recompute` runs every rule for every user and upserts `user_values`;
   `GET /values` paged; `ValueStore.matrix()` returns a pandas-friendly `FeatureMatrix`;
   `GET /users/{id}/features` groups the user's values by `rule.feature` and adds `tier` from `TierStore`
   (only `passed` tiers). Implement the `TierStore` repository. Also recompute a user's values right
   after ingest for that user (cheap: one user's history), so the fast loop sees fresh values.
   *Done when:* integration test: 3 users, 2 rules → expected matrix; profile groups values by feature.
7. **Demo data loader** (helps everyone) — `scripts/load_demo_events.py`: registers Lumen features
   `background` (bg_remove), `ai_enhance` (ai_enhance with `edits_left` prop), `hd_export`
   (export_hd_attempt, pt_track_hd_export_blocked; `plans: ["premium"]`) and event types
   (`photo_import`, `bg_remove`, `ai_enhance`, `export`, `export_hd_attempt`, `pt_track_hd_export_blocked`, `edit_abandoned`) and
   generates synthetic events for the first 200 seed users consistent with their `ai_edits_first_day`
   (label them synthetic in `props.synthetic=true`). *Done when:* recompute produces non-empty values.

## Tests you must have
Idempotency (same id twice), counter increments only on insert, unknown key rejected, every rule
measure incl. `ratio`/`sum`/`last`/`where`, window boundary, default rules created with a feature,
feature profile grouping, `MembershipSync` called once per batch after commit, matrix shape, SDK flush
+ retry keeps ids, SDK refuses strings >100 chars in props (dev warning) so prompts never leave the app.

## Pitfalls
- Two timestamps: windows use `occurred_at`; `received_at` is only for debugging lag.
- SQLite + async: use `aiosqlite`; enable WAL (`PRAGMA journal_mode=WAL`) for concurrent reads during demo.
- Don't let `user_action_counts` drift: no counter update outside the ingest transaction.
- Props are not for free text. If a teammate asks to store a prompt, store its length or a category the app computes.
- B and C start before you finish: publish the `FeatureMatrix` shape and a fake `ValueStore` in
  `tests/fakes.py` early (chapter 1), so they can work against it.

# Role A — Ingest & Rules (backend)

**Mission:** events go in reliably, values come out. You own the data plane: SDK → catalog → event
history → rules → per-user values. Everyone else reads what you produce.

## You own
`sdk/js/**` · `feature_signal/api/v1/{events,catalog,rules,values}.py` ·
`feature_signal/repositories/{event_types,events,rules,values}.py` ·
`feature_signal/services/{ingest,rule,value}_service.py` · `feature_signal/domain/rules.py` ·
`feature_signal/db/**` (all tables and Alembic migrations, including tables others need) ·
`tests/**/test_{ingest,events,catalog,rules,values}*.py` · `docs/ingest/**`.

## Inputs / outputs
- In: HTTP from the SDK and dashboard (contract: `docs/contracts/api.md`, owner A rows).
- Out: `ValueStore.matrix(app_id)` → `FeatureMatrix` (one row per `customer_user_id`, one column per
  rule key) — B ranks it, C reads values to write `p_*` attributes. Keep this port stable.

## Chapters (in order; each ends with the `chapter-done` skill)
1. **Tables + migration** — `event_types(app_id, action_id PK int, key, name, description, family, created_at)`,
   `events(event_id PK uuid, app_id, customer_user_id, action_id, occurred_at, received_at, props JSON, decision_id NULL)`
   with one index `(app_id, customer_user_id, occurred_at)`, `user_action_counts(app_id, customer_user_id,
   action_id, n, last_ts)` PK `(app_id, customer_user_id, action_id)`, `rules(...)`, `user_values(app_id,
   customer_user_id, rule_key, value, computed_at)` PK `(app_id, customer_user_id, rule_key)`. Also add
   C's `proposals` and `decisions` tables (columns from the Proposal/Decision schemas, JSON columns for
   nested parts). Integer `action_id`, never the string key, in `events`.
   *Done when:* `alembic upgrade head` creates everything; integration test inserts and reads one row per table.
2. **Catalog** — `POST/GET /event-types`; upsert by `key`. *Done when:* re-registering a key updates it (200), test covers both.
3. **Idempotent ingest** — `POST /events`. In ONE transaction: insert into `events` with
   `ON CONFLICT(event_id) DO NOTHING`; increment `user_action_counts` **only for rows actually inserted**
   (use the insert's rowcount / RETURNING). Unknown keys → `unknown_keys`. Max 500 per batch.
   *Done when:* curl sends an event, it is in the DB; same `event_id` twice → `duplicates: 1` and the counter unchanged (test).
4. **SDK** — `sdk/js/src/index.ts`: `init({ baseUrl, appId, customerUserId })`, `registerEventType(...)`,
   `track(key, props?)` (generates `event_id` with `crypto.randomUUID()`, sets `occurred_at`, buffers,
   flushes every 2 s or 20 events, retries with the same ids). ~50 lines, no deps. Build with `tsc`.
   Vitest unit test with a fake fetch. *Done when:* D can `import { track } from '../../sdk/js'` and events arrive.
5. **Rules engine** — `domain/rules.py`: `apply(rule: RuleDefinition, events: list[Event], now) -> float`
   for `count`, `distinct` (by `props[distinct_prop]`), `exists`, `days_active`, with `window_days`
   using `occurred_at` (never `received_at`). Pure function. `POST/GET /rules`.
   *Done when:* unit tests for each measure + window edge (event exactly at the boundary) pass.
6. **Values** — `POST /values:recompute` runs every rule for every user and upserts `user_values`;
   `GET /values` paged; `ValueStore.matrix()` returns a pandas-friendly `FeatureMatrix`.
   *Done when:* integration test: 3 users, 2 rules → expected matrix.
7. **Demo data loader** (helps everyone) — `scripts/load_demo_events.py`: registers Lumen event types
   (`photo_import`, `bg_remove`, `ai_enhance`, `export`, `export_hd_attempt`, `edit_abandoned`) and
   generates synthetic events for the first 200 seed users consistent with their `ai_edits_first_day`
   (label them synthetic in `props.synthetic=true`). *Done when:* recompute produces non-empty values.

## Tests you must have
Idempotency (same id twice), counter increments only on insert, unknown key rejected, rule measures,
window boundary, matrix shape, SDK flush + retry keeps ids.

## Pitfalls
- Two timestamps: windows use `occurred_at`; `received_at` is only for debugging lag.
- SQLite + async: use `aiosqlite`; enable WAL (`PRAGMA journal_mode=WAL`) for concurrent reads during demo.
- Don't let `user_action_counts` drift: no counter update outside the ingest transaction.
- B and C start before you finish: publish the `FeatureMatrix` shape and a fake `ValueStore` in
  `tests/fakes.py` early (chapter 1), so they can work against it.

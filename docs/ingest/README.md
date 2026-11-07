# Ingest & Rules (A) — what is ready for you

Everything below is on `main`, tested, and follows `docs/contracts/api.md`. Chapters: `01`–`07` in this folder.

## Endpoints (real, not 501)
| Endpoint | Chapter |
|---|---|
| `POST/GET /v1/apps/{app_id}/features` | 02 |
| `POST/GET /v1/apps/{app_id}/event-types` | 02 |
| `POST /v1/apps/{app_id}/events` | 03 |
| `GET /v1/apps/{app_id}/users/{id}/timeline` | 04 |
| `POST/GET /v1/apps/{app_id}/rules` | 05 |
| `POST /v1/apps/{app_id}/values:recompute`, `GET …/values` | 06 |
| `GET /v1/apps/{app_id}/users/{id}/features` (feature profile) | 06 |

## For B (Brain)
- `ValueStore`: `feature_signal.repositories.values.ValueRepository(session).matrix(app_id)` → `FeatureMatrix`
  (sorted users × sorted rule keys, missing = 0).
- `TierStore`: `feature_signal.repositories.tiers.TierRepository(session).put_many(app_id, tiers)` replaces
  the app's tiers with your latest run; `list()` reads them.
- `RuleRepo` / `EventTypeRepo` / `FeatureRepo`: `repositories/{rules,event_types,features}.py` — the LLM prompt
  can read features, events and descriptions from there. Your suggested rules are validated on save
  (`422 unknown_event_key` / `unknown_feature`).
- Rule evaluation is `feature_signal.domain.rules.apply(definition, events, now)` (pure) if you need it offline.

## For C (Adapty & Proposals)
- Fast loop: ingest stores events, recomputes those users' values, then calls `app.state.membership_sync`
  (your `MembershipSync`) in the background with the batch's users. Register it in `main.py:create_app()`
  (contract-change). Until then it is a no-op.
- Tables for you already exist (`db/tables.py`): `proposals`, `decisions`, `app_settings`,
  `adapty_attribute_state` (last attributes written per user, so you PATCH only diffs).
- Feature `plans` (for `feature_not_in_plan`): `FeatureRepository(session).list(app_id)`.

## For D (Dashboard & Demo)
- Real SDK: point the alias and `tsconfig` path from `./src/sdk-stub.ts` to `../sdk/js/src/index.ts`
  (same exports: `init`, `registerEventType`, `track`; extra: `registerFeature`, `flush`, `setUser`).
  `track()` sends every 2 s; call `await flush()` after a demo click if you want the timeline to update at once.
- Timeline and profile for the side panel: `GET …/users/{id}/timeline?limit=20` and `GET …/users/{id}/features`.
- CORS allows `http://localhost:5173` (`CORS_ORIGINS`).

## Shared test fixtures
`tests/integration/conftest.py`: `db_url` (a migrated SQLite file) and `api` (TestClient on it). Set
`api.app.state.membership_sync = fake` to observe the fast loop.

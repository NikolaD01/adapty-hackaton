# Contract changes

Append newest first. Every change to a shared file (CLAUDE.md §6) gets a line here in the same PR.

| Date | Area | Change | Who acked |
|---|---|---|---|
| 2026-11-08 | adapty | Lookup result gains optional `audience_name`, `ab_test_name`, `arms` (an A/B test returns every arm; `flow_*` is the largest, not the user's arm); lookup retries with the Android platform on `INCORRECT_SEGMENT_HASH_ERROR`; wiring moved from module import to the server lifespan (`wire_running_app`), so importing `main.py` (tests) reaches nothing | pending |
| 2026-11-08 | adapty | `main.py` also calls `wire_brain` (configures B's runtime for the running app, flows read from Adapty by name); B's trigger placement `settings` is now `settings_upgrade` (the placement's name in the Adapty app); proposals of one batch keep their order | pending |
| 2026-11-08 | brain | Outcome window is a setting: `build_outcomes(window_days=90)`, `BrainRuntime.outcome_window_days`; `expected_effect.metric` is `net_revenue_<N>d` (pattern, was the literal `net_revenue_90d`); field names `*_90d` unchanged; demo uses 30 | pending |
| 2026-11-08 | contracts | Documented the existing B→C interface `evidence.segment_conditions` (fields, ops) in api.md | pending |
| 2026-11-08 | ingest | Optional `INGEST_API_KEY` / `X-Api-Key` on writes (off by default), SDK `init({ apiKey })`; `make demo`, `make demo-reset` | pending |
| 2026-11-08 | ingest | New `POST /adapty-webhook` (A), setting `ADAPTY_WEBHOOK_AUTH`, default rule `adapty_net_revenue_90d`; router mounts `adapty_webhook` | pending |
| 2026-11-08 | adapty | `main.py` sets `app.state.membership_sync` and `app.state.attribute_writer` for the running app when `ADAPTY_SECRET_KEY` is set (not in `create_app()`, so tests never write to Adapty) | pending |
| 2026-11-08 | ingest | `make offline-data` also copies `lumen_dataset.json.gz`; `make demo-events`; `data/*.json.gz` ignored | pending |
| 2026-11-08 | ingest | Ingest calls `app.state.membership_sync` (set by C in `create_app`) in the background after commit | pending |
| 2026-11-08 | ingest | `alembic.ini` owned by A; `docker compose up api` runs `alembic upgrade head` first; tables `app_settings` and `adapty_attribute_state` added for C; rule key max 80 chars (was 40); shared `tests/integration/conftest.py` (`db_url`, `api` fixtures); stored times are timezone-aware UTC (`UtcDateTime`); routes use `Annotated[..., Depends(...)]` | pending |
| 2026-11-08 | contracts | Feature model: `features` resource with `plans` and default rules; event `features` list replaces `family`; typed `props` (no free text); measures `ratio`/`sum`/`last`/`max`/`min` + `where`; feature profile route; `tiers` + `hypotheses` in InsightRun; Adapty keys = `p_segment` + `f_<feature>_tier` (drops `p_tier`, `p_top_feature`, `p_top_feature_count`, `p_score`); proposal `adapty_filters`, `highlight_feature`, `needs_publish`, status `awaiting_publish`; `membership:sync` + `MembershipSync`/`TierStore`/`FeatureRepo` ports | team (PR #3) |
| 2026-11-07 | contracts | v1 frozen: endpoints, schemas, ports, Adapty attribute keys | team |

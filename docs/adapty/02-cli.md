# 02 — Adapty CLI adapter

**Area:** C · **Branch/PR:** `adapty/cli-adapter` · **Date:** 2026-11-08

## What
`SubprocessAdaptyCli` runs `adapty ... --json` and returns parsed JSON (the `AdaptyCli` port).
`AdaptyCommands` wraps the commands activation and the paywall draft need.

## Why
Segments, audiences, A/B tests and flows can only be changed through the CLI. One adapter means one place
that checks what the CLI does not.

## How it works
1. `integrations/adapty/cli.py:SubprocessAdaptyCli.run(*args)` splits `Settings.adapty_cli` (`adapty` or a
   docker compose command) with `shlex`, adds `--json`, runs it with `create_subprocess_exec` (no shell) and a
   timeout. Exit code ≠ 0 → `ApiError(502, "adapty_cli_failed")` with stderr; non-JSON → `adapty_cli_bad_output`;
   missing binary → `adapty_cli_missing`; timeout → `504 adapty_cli_timeout`. A JSON list is wrapped as `{"data": [...]}`.
2. `custom_attribute_filter("p_segment", ["x"])` → `attributes__p_segment@string:IN:x`.
   `condition_to_filter(Condition)` turns a proposal's `adapty_filters` entry into a `--filter` (JSON form when a value has a comma).
3. `AdaptyCommands`: `segments_create` (≥1 filter), `find_segment_by_title` (pages of 100),
   `placement_by_developer_id`, `placements_update` (needs `--developer-id`; audiences must all carry
   `content_type`, default audience last), `ab_tests_create` (weights sum to 100, one segment, draft),
   `ab_tests_start` (`--yes`, cannot be undone), `flows_get/config_get/create/config_update` (config via temp file),
   `flows_publish` (refused unless `confirmed_by_human=True`).

## Contract touched
Port `AdaptyCli` unchanged. CLI behaviour verified on 2026-11-08 with `--help` and read-only calls on the Lumen app.

## How to test
```bash
docker compose run --rm test
```
Expected: `125 passed` (about 30 in `tests/unit/test_adapty_cli.py`) and `39 tasks, 0 problems`.
Read-only manual check on the host CLI: `placements list/get`, `segments list/get`, `flows list`, `ab-tests list` all
return `{"data": [...]}` or the object as the tests assume.

## Facts found here (for CLAUDE.md §5, shared file, via contract-change)
- "No active subscription" is the field `subscription_state` with values `never_subscribed`, `subscription_cancelled`
  (full list in the `audiences` skill). Use it in `adapty_filters`; values are not validated by the server.
- Placement audiences from `placements get` have `content_type` `flow` or `flow_ab_test`; entries of a running
  test must be sent back unchanged or the test stops without a winner.
- `ab-tests start` needs `--placement` and `--segment` (or `--all-users`) and `--yes` when output is JSON.

## Limits / not claimed
- No test starts a real process against Adapty; `segments create` and `ab-tests start` were not run here.
- The docker-compose CLI is not logged in yet (`docker compose run --rm adapty-login`, browser step).

## Status
Done · Next: C6 — served-flow lookup

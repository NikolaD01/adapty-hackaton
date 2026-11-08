# Role C — implementation plan

> Format: superpowers "writing-plans". Every task is test-first: write the failing test, run it and see it
> fail, write the smallest code that passes, run the whole suite, commit. One task = one branch = one PR.

**Goal:** close the loop inside Adapty: a proposal becomes attributes on profiles, a segment, an audience and
an A/B test with a control arm, after a human approves (or autopilot, within limits).

**Architecture:** ports and adapters. Adapty I/O lives only in `integrations/adapty/` (HTTP client, CLI
wrapper, lookup). Services in `services/` take ports in the constructor, so every service test runs on the
fakes in `tests/fakes.py` and never touches the network. The API layer in `api/v1/` only maps HTTP to
services and `ApiError`.

**Tech:** Python 3.11, FastAPI, httpx (`MockTransport` in tests), SQLAlchemy async (tables owned by A),
pytest, ruff, Adapty CLI 0.18.0 in the Docker image.

**Run everything with:** `docker compose run --rm test` (ruff check, ruff format --check, pytest,
`tools/tasks.py check`). Expected at the end of every task: all green.

**Rules for every task**
- Only C's files (`docs/team/C-adapty-proposals.md`, "You own"). A contract change goes through `contract-change`.
- Branch `adapty/<task>`, Conventional Commits, no AI attribution (CLAUDE.md).
- `python3 tools/tasks.py set <id> doing` at start, `done` at the end; chapter doc in `docs/adapty/NN-*.md`.
- Nothing irreversible on the live account without the user's explicit yes: `segments create` (cannot be
  deleted from the CLI), `ab-tests start` (cannot be undone), `flows publish`. Attribute writes only on
  test profiles (`fs_*` / `pulse_test_*`), never on all seed users.

---

## Phase 0 — done

### Task C1: Profile client (`AttributeWriter`) — DONE, not yet committed
**Files:** `feature_signal/integrations/adapty/profile_client.py`,
`tests/unit/test_adapty_profile_client.py`, `docs/adapty/01-profile-client.md`.
- [x] Tests first: list body, PATCH and headers; `None` → `null`; numbers stay numbers; limits (key 30,
  value 50, 30 attributes, bool, NaN) fail **before** sending; 429 with `Retry-After`; 5xx with growing
  delay; network error retried; gives up after N attempts; 400 not retried; the secret never in an error.
- [x] Implementation; suite green (42 passed).
- [x] Manual: one test profile, write text + number, delete a key, read back, clean up.
- [ ] Commit `feat(adapty): profile client for custom attributes`, push, PR.

---

## Phase 1 — tasks with no dependencies (can start now)

### Task C2: Adapty CLI adapter (`AdaptyCli`)
**Files:** create `integrations/adapty/cli.py`, `tests/unit/test_adapty_cli.py`, `docs/adapty/02-cli.md`.

- [ ] **Step 1 — failing tests** (a fake runner records argv and returns canned stdout/rc):
  - `test_command_prefix_comes_from_settings` — `ADAPTY_CLI="docker compose ... adapty"` is split into argv.
  - `test_every_call_adds_json_flag_and_parses_stdout`.
  - `test_nonzero_exit_raises_api_error_with_stderr` — `ApiError(502, "adapty_cli_failed")`.
  - `test_segments_create_builds_filter_args` — `attributes__p_segment@string:IN:power_editor` plus each
    `adapty_filters` entry, all ANDed.
  - `test_placements_update_sends_full_list_and_developer_id` — read → modify → write; segment audience at
    priority 0, default audience stays last; missing `--developer-id` is refused before running.
  - `test_ab_tests_create_then_start` — create as draft, start only by id.
  - `test_flows_methods_build_expected_argv` — `flows get/create/config update/publish`.
- [ ] **Step 2 — run, expect fail** (`ModuleNotFoundError: ...cli`).
- [ ] **Step 3 — implement** `AdaptyCliAdapter.run(*args)` over `asyncio.create_subprocess_exec` (no shell),
  plus thin typed methods. Timeout per call.
- [ ] **Step 4 — run, expect green.**
- [ ] **Step 5 — manual, read-only:** `placements get`, `segments list`, `flows list` on the chosen app.
  Check the exact argv of `segments create` / `placements update` with `--help` (CLAUDE.md §5 says the
  `audiences` skill has the real syntax). Record the "no active subscription" field name in CLAUDE.md §5.
- [ ] **Step 6 — commit** `feat(adapty): CLI adapter`.

### Task C6: Served-flow lookup (`FlowLookup`, `POST /lookup`)
**Files:** create `integrations/adapty/lookup.py`, `services/lookup_service.py`; fill `api/v1/lookup.py`;
tests `tests/unit/test_adapty_lookup.py`, `tests/api/test_lookup_api.py`.

- [ ] **Step 1 — failing tests** (httpx `MockTransport`):
  - `test_reads_segment_hash_from_profile`.
  - `test_calls_variations_endpoint_with_md5_of_placement_and_hash` — path
    `/api/v1/sdk/in-apps/<key prefix>/flow/variations/<placement>/<md5(placement:segment_hash)>/?disable_cache`
    and the four `ADAPTY-SDK-*` headers.
  - `test_returns_flow_id_and_name`; `test_unknown_user_returns_none_flow_not_500`.
  - API: `test_lookup_returns_one_result_per_user`, `test_empty_list_is_422`.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement**, reusing the request shape from the reference script (ask the developer for
  `pulse_validate.py`; fallback `seed_adapty.py`).
- [ ] **Step 4 — green.**
- [ ] **Step 5 — manual:** two users, one with `p_segment` set and one without → different `flow_id`
  (needs a segment from C4; until then: same flow for both, which also proves the call works).
- [ ] **Step 6 — commit** `feat(adapty): served-flow lookup`.

---

## Phase 2 — state and the fast loop

### Task C3: Proposals store, API and settings
**Depends on:** A1 (tables). Until A merges them: an in-memory repository behind the same interface, and the
column list sent to A (`contract-change`).
**Files:** `repositories/proposals.py`, `services/proposal_service.py`, `api/v1/proposals.py`,
`api/v1/settings.py`; tests `test_proposal_service.py`, `test_proposals_api.py`.

- [ ] **Step 1 — failing tests:**
  - `test_create_many_from_drafts_sets_status_draft_created_by_ai` (implements `ProposalSink`).
  - `test_state_machine_allows_only_contract_transitions` — draft→approved→executing→live|failed,
    draft→rejected, executing→awaiting_publish→live; everything else `409 invalid_transition`.
  - `test_patch_whitelist` — only `holdout_pct, cooldown_days, flow_id, condition_value,
    trigger_placement`; unknown field → 422; each change appended to `edits` with from/to.
  - `test_patch_only_in_draft`; `test_reject_requires_reason`.
  - `test_settings_default_human`; `test_put_settings_validates_mode_and_limits`.
- [ ] **Step 2–4** — fail, implement, green.
- [ ] **Step 5 — commit** `feat(proposals): store, edit, reject and settings`.

### Task C9: Membership sync (fast loop, `MembershipSync`)
**Depends on:** C1 (done), C3 (live proposals), A7/B2 by contract (`TierStore`, `ValueStore`).
**Files:** `services/membership_service.py`, `api/v1/membership.py`; tests `test_membership_service.py`.

- [ ] **Step 1 — failing tests** (fake `TierStore`, `ValueStore`, `FakeAttributeWriter`):
  - `test_unchanged_user_writes_nothing`.
  - `test_user_crossing_a_tier_writes_one_key`.
  - `test_user_leaving_the_segment_gets_p_segment_null`.
  - `test_only_passed_features_are_written_max_10`.
  - `test_first_matching_live_proposal_wins`.
  - `test_none_ids_means_every_user_with_values`; `test_result_counts_checked_changed_written`.
  - `test_writes_respect_concurrency_limit`.
- [ ] **Step 2–4** — fail, implement (last written attributes kept per user; diff; PATCH only changed keys).
- [ ] **Step 5 — manual:** one test profile crosses a tier → one PATCH; read profile back.
- [ ] **Step 6 — commit** `feat(membership): sync only changed attributes`.

---

## Phase 3 — approve runs in Adapty

### Task C4: Activation on approve
**Depends on:** C1, C2, C3, C9.
**Files:** `services/activation_service.py`, `repositories/decisions.py`; tests `test_activation_service.py`.

- [ ] **Step 1 — failing tests** (fake CLI, fake writer):
  - `test_step_order` — membership sync → `segments create` → read placement → A/B test (control = current
    default flow with `holdout_pct`, B = `action.flow_id`) create → start → decision log.
  - `test_segment_filters_are_p_segment_and_adapty_filters`.
  - `test_reapprove_reuses_segment_by_title_fs_segment_key` (idempotent).
  - `test_needs_publish_stops_with_awaiting_publish_before_ab_test`.
  - `test_failed_step_sets_failed_and_logs_error_step`.
  - `test_every_step_logged_ok_or_error`.
- [ ] **Step 2–4** — fail, implement, green.
- [ ] **Step 5 — manual, only after the user's yes:** on a separate test placement, approve one proposal and
  see the segment and the A/B test in the Adapty dashboard; `/lookup` for a user in and out of the segment.
- [ ] **Step 6 — commit** `feat(activation): approve creates segment and A/B test`.

### Task C5: Decision log API
- [ ] Tests: `test_decisions_listed_newest_first`, `test_entry_shape_matches_contract`.
- [ ] Implement `GET /apps/{app_id}/decisions`; green; commit `feat(decisions): decision log API`.

---

## Phase 4 — autopilot and the paywall draft

### Task C7: Autopilot mode
- [ ] **Failing tests:** `test_autopilot_approves_drafts_with_decided_by_autopilot`,
  `test_autopilot_never_publishes_flows`, `test_respects_max_live_proposals`,
  `test_raises_holdout_to_min_holdout_pct`, `test_human_mode_does_nothing`.
- [ ] Implement as a service that runs `ActivationService` on new drafts when `mode = autopilot`.
  No LLM call anywhere. Green; commit `feat(autopilot): bounded auto-approve`.

### Task C8: Paywall draft from the live config
**Depends on:** C2; B6 (`LLMProvider.paywall_copy`) by contract — tests use a fake LLM.
- [ ] **Failing tests:** `test_copies_live_config_and_changes_only_known_paths`,
  `test_refuses_feature_not_in_plan_422`, `test_invalid_llm_output_falls_back_to_edited_copy`,
  `test_sets_flow_id_and_needs_publish_true`, `test_never_calls_publish`.
- [ ] Implement `POST /proposals/{id}/paywall-draft` (`flows config get` → change title/products →
  validate → `flows create` + `config update`). Green.
- [ ] Manual: one draft flow with the new title appears in Adapty (a draft is not visible to users).
- [ ] Commit `feat(paywall): draft flow from live config`.

---

## Phase 5 — finish
- [ ] Every chapter doc in `docs/adapty/`, C's row in `docs/STATUS.md`, all C tasks `done` in the graph.
- [ ] With A and B merged: one real run end to end (click in the demo → tier changes → sync → segment →
  `/lookup` shows the other flow). This is milestone S2; it needs A and B, not only C.

## Open decisions (from the user, before Phase 3)
1. Which Adapty app: Lumen `9ccde368` (our account) or `c6c7bdd1` (repo default).
2. Permission for one real segment and one started A/B test on a separate test placement.

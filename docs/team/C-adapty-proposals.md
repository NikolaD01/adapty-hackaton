# Role C — Adapty & Proposals (backend) — the riskiest part, start first

**Mission:** close the loop inside Adapty. A proposal becomes attributes on profiles, a segment, an
audience on a placement and an A/B test with a control arm — after a human approves (or autopilot,
within limits). Without this phase we have no proof that we use Adapty, which is a third of the grade.

## You own
`feature_signal/integrations/adapty/**` (`profile_client.py`, `cli.py`, `lookup.py`, `models.py`) ·
`feature_signal/services/{proposal,activation,paywall,lookup}_service.py` ·
`feature_signal/api/v1/{proposals,settings,decisions,lookup,membership}.py` · `feature_signal/services/membership_service.py` ·
`feature_signal/repositories/{proposals,decisions}.py` (tables are created by A in `db/tables.py` —
send A the columns or do it via `contract-change`) · `tests/**/test_{adapty,proposal,activation,paywall,lookup}*.py` · `docs/adapty/**`.

## Inputs / outputs
- In: drafts from B (`ProposalSink`), values from A (`ValueStore`), human actions from D (PATCH/approve/reject).
- Out: real changes in the Lumen Adapty app; decision log; lookup results for the demo.

## Chapters
1. **Profile client** — `AttributeWriter` over httpx: PATCH, body `{"custom_attributes":[{"key","value"}]}`,
   validate key ≤30 / value ≤50 / ≤30 attributes **before** sending; `value=None` deletes; retries on
   429/5xx. *Done when:* unit test asserts the exact payload (list, not object) with a mock transport;
   one manual run on ONE test profile (create `pulse_test_*`, never touch all 6,000).
2. **CLI adapter** — `AdaptyCli` wraps `adapty ... --json` via subprocess; command prefix from
   `ADAPTY_CLI` env (`adapty`, or `docker compose -f ../docker-compose.yml run --rm -T dev adapty`).
   Methods: `segments_create(title, filters)` with `attributes__p_segment@string IN [...]`,
   `placements_get`, `placements_update(id, developer_id, title, audiences)` (always read → modify →
   write the full list; segment audience priority 0, default stays last), `ab_tests_create/start`,
   `flows_get/create/config_update/publish`. *Done when:* tests with a fake runner assert argv;
   manual run creates a segment visible in the dashboard.
3. **Proposals + modes** — store drafts from B; `GET/POST /proposals`, `PATCH` (allowed fields only,
   every change appended to `edits`), `:reject` (reason), `GET/PUT /settings` (`human` default).
   *Done when:* service tests for state transitions and the PATCH whitelist.
4. **Activation (approve)** — `ActivationService.execute(proposal)`: (1) run the membership sync for
   all users with values (writes `p_segment` and the passed `f_<feature>_tier` keys) — batch with a
   concurrency limit; (2) `segments create` with `attributes__p_segment@string IN [<key>]` **and** the
   proposal's `adapty_filters` (map "no active subscription" to the real Adapty field — check the
   `audiences` skill / `segments get` on the built-in segments; record the field in CLAUDE.md §5);
   (3) A/B test on the trigger placement: arm A = existing
   default flow (control, `holdout_pct`), arm B = `action.flow_id`; create as draft, then start;
   (4) decision log with every step `ok`/error; status `live` or `failed`. Idempotent: re-approving
   doesn't duplicate segments (look up by title `[fs] <segment_key>`). If `action.needs_publish` (a new
   draft flow): stop before the A/B test with status `awaiting_publish`; when the flow is published
   (human), continue. In autopilot: same, `decided_by=autopilot`, never publish flows, respect
   `max_live_proposals`. *Done when:* fake-port test of the full sequence
   and a manual run on Lumen shows the segment + test in the dashboard.
5. **Lookup** — `POST /lookup`: GET the profile (segment_hash) and call the SDK flow-variations
   endpoint (`/api/v1/sdk/in-apps/<key prefix>/flow/variations/<placement>/<md5(placement:segment_hash)>/?disable_cache`,
   headers `ADAPTY-SDK-PROFILE-ID`, `ADAPTY-PROFILE-SEGMENT-HASH`, `ADAPTY-SDK-PLATFORM`,
   `ADAPTY-SDK-VERSION`). Reference implementation: `workspace/validation/pulse_validate.py` (outside
   this repo, ask the developer). *Done when:* two users in/out of the segment return different `flow_id`.
6. **Paywall draft (Phase 5)** — copy the live flow config (`flows config get`), change title + product
   list at known paths only, validate, `flows create` + `config update` as a new draft. LLM only writes
   the title text (port from B). Refuse (`422 feature_not_in_plan`) when `highlight_feature` is not in
   `plans` of an offered product (`FeatureRepo`). The proposal then gets `action.flow_id = <draft>` and
   `needs_publish = true`. Publishing = human. *Done when:* a draft flow exists in Adapty with the new title.
7. **Membership sync (the fast loop)** — `MembershipService.sync_users(app_id, ids)`: per user compute
   the passed `f_<feature>_tier` values (`TierStore` + `ValueStore`) and `p_segment` (first live
   proposal whose condition matches, else `null`); keep the last written attributes per user (small
   table or cache) and PATCH **only changed keys**; same limits validation as chapter 1. Expose
   `POST /membership:sync`; implement the `MembershipSync` port that A calls after ingest, and register it
   with `app.state.membership_sync = ...` in `main.py:create_app()` (contract-change; A's ingest already
   calls it in the background, see `services/ingest_service.py:run_membership_sync`).
   *Done when:* fake-port tests: unchanged user → 0 writes; user crosses a tier → 1 write; user leaves
   the segment → `p_segment: null`; manual: clicking in the demo app moves a test user into the segment
   and `/lookup` shows the other flow.

## Tests you must have
Attribute payload shape and limits · PATCH whitelist · state machine incl. `awaiting_publish` ·
activation step order and idempotency (fake CLI) · segment filters = `p_segment` + `adapty_filters` ·
audiences list keeps the default audience last · autopilot never publishes · sync writes only diffs ·
paywall draft refuses a feature the plan doesn't include.

## Pitfalls
- The placement can't be emptied; control = default flow. Read the placement before writing.
- `placements update` requires `--developer-id`; a missing flag fails silently in scripts — check rc.
- The SDK cache serves the old flow until the profile refreshes; the demo uses `/lookup`.
- Never write attributes to all seed users in a loop during development; use a small list.
- Old keys `p_tier`, `p_top_feature`, `p_top_feature_count`, `p_score` are dropped from the contract — don't write them.
- Leftovers on the account from validation: segment `[pulse-test] p_persona=power_editor`, placement `pulse_test` — don't reuse.

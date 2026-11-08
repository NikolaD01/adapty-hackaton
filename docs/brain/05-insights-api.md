# 05 — Insight runs and proposal drafts

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What
Implement `POST /insights:run` and `GET /insights/latest`, persist measured tiers through A's adapter,
and hand eligible drafts to C's `ProposalSink`.

## Why
The dashboard needs one reproducible numerical result; C needs measured, app-specific proposal inputs.

## How it works
`InsightService` loads outcomes, ranks values, derives tiers/segments, and compares randomized arms.
CPU work runs outside the event loop. One process-local lock serializes runs for each app. The latest
run is cached only after tier/proposal writes and the request transaction commit succeed. Responses
are copies, so callers cannot mutate the cached run.

Drafts require a one-sided positive interval and an explicitly verified published flow ID. The existing
condition is `p_segment IN [segment_key]`; native equality filters become `IN [value]` to match the frozen
proposal schema. Behavioral predicates remain in `evidence.segment_conditions`; full predicates are retained in
`evidence.analysis_conditions`. C consumes the behavioral predicates for membership; B does not write attributes or activate audiences. A highlight is
included only when the supplied flow metadata explicitly confirms that feature belongs in that flow.

The B-owned route uses real `ValueRepository`, `TierRepository`, and `RuleRepository`. Its composition
hook is `configure_brain(app, app_id, BrainRuntime(...))`. Required inputs are an explicit cutoff,
a `proposal_sink_factory(session)` implementing C's port, and app-specific verified published-flow
metadata. Optional inputs are the dataset adapter, verified offline feature mapping, verified live
identity/window metadata, and explanation enablement. The default dataset path comes from Settings.
Each runtime is app-scoped; never reuse another app's flow IDs or historical mappings.

C's composition code can construct a `BrainRuntime` and call `configure_brain` after `create_app()`.
Use C's real `ProposalService(session)` sink and the same request session. That service commits its
batch internally; B does not own the sole transaction boundary. The public
routes return `503 brain_not_configured` until this composition is supplied; no fake is installed in
production. Missing latest results return `404 insight_not_found`; invalid data returns a 422 envelope.

## Contract touched
No shared schema, port or application entrypoint changed. This supplies implementations behind B's
existing routes. Runtime composition is internal Python wiring. Latest results live for one process;
tiers and C's drafts use their respective stores.

## How to test
```bash
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev pytest -q -p no:cacheprovider tests/service/test_insight_service.py tests/integration/test_insight_api.py
```
Tests cover source validation, app isolation, schema-compatible drafts, published-flow checks, no-signal
runs, failed sink handoff, latest-run copies, and real SQLite tier/value adapters. The proposal sink is
faked. No test writes to Adapty.

## Limits / not claimed
C3 proposal storage is not on the reviewed main baseline. An isolated, network-disabled test using C commit `d0c208d1597d34c34f148d18bfde81e26d976ce3`
ran the real B service with real A repositories and C's sink: three drafts persisted and were returned
by C's GET route. App isolation, full payload shape and membership through a fake attribute writer passed.
Production composition and activation remain integration handoffs, not verified end-to-end behavior. Nontransactional injected sinks must provide their own failure guarantees.
Offline cut points must not be attached to differently defined live rules merely because names look alike.
Refunds and synthetic/source provenance are present in proposal evidence/reasons and CLI diagnostics;
the frozen insight schema has no separate fields for them.

## Status
B implementation and contract tests complete. C3 composition and membership integration remain to be verified.

# 06 — Validated rule suggestions

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What

The OpenAI adapter proposes schema-validated measurements from declared feature and event metadata.
The service returns suggestions without saving them. Humans accept rules through A's rules endpoint.

## Why

Composed behavioral measures can reveal useful hypotheses without allowing a language model to rank
users, choose thresholds, set tiers, or decide which offer to show.

## How it works

`RuleSuggestService` reads feature, event-type and rule repositories for the requested app.
It creates an immutable `SuggestionContext` containing feature descriptions, existing/default rules,
and an explicit per-event property allowlist. A request-scoped provider factory receives that context;
the shared `LLMProvider` method signatures stay unchanged.

The catalog does not declare property types. Callers must explicitly supply a mapping such as
`{"declared_event": {"tokens_left": "number", "photo_id": "label"}}`. These are examples of metadata,
not built-in telemetry assumptions. Supported kinds are `number`, `label` (a short categorical label),
and `boolean`. With no allowlist, property-based suggestions are rejected. No user event payloads or
free-text properties are supplied to the model.

`OpenAILLMProvider` receives Settings and an injected asynchronous OpenAI client. It uses
`client.responses.parse` with private Pydantic output schemas, the configured model, a 4,000-token output
bound, a 30-second request timeout, and `store=False`. The composition layer owns client credentials,
client retry policy and lifecycle. Use `max_retries=0` for a single bounded manual smoke call.

Validation checks schema shape, declared events and features, event membership in the selected feature,
measure-specific arguments, typed properties on every relevant event, and compatible `where` values.
Rules with extra measure arguments are rejected. Duplicate keys and normalized definitions are removed
against existing rules and the current batch. Returned rules always have `source="ai"`.

Supported measures follow the contract: count, distinct, exists, days_active, ratio, sum, last, max and
min. Ratios require declared denominator events; numeric aggregation requires declared numeric props.
The blocked-HD demo uses `pt_track_hd_export_blocked`, `exists`, and a seven-day window.

Provider errors, refusals, incomplete responses and malformed output yield no suggestions. The service
revalidates alternate/fake provider output as well. A malformed structured response rejects the response;
semantically invalid rules are individually omitted.

Explanations render all measured ranking numbers locally. Model summaries are discarded. Generated
hypotheses must exactly match one of three vetted tentative observational statements. Any additions,
causal/offer recommendations or unsupported confidence prose trigger deterministic fallback. Model
confidence is discarded and public confidence is always zero: no calibrated hypothesis confidence
exists in the contract. Ranking inputs remain unchanged. Suggestion rationales are rendered locally
from the validated measure and window; model rationale prose is never returned.

Paywall copy can edit only existing top-level string `title` and `subtitle` fields. It preserves numeric
and billing fields and returns a deep copy. Numeric copy and explicit pricing, billing or entitlement
claims trigger unchanged-copy fallback. Nested paywall schemas fall back unchanged. C owns configuration
changes, validation and publication.

## Contract touched

Consumes the unchanged `LLMProvider`, `FeatureRepo`, `EventTypeRepo` and `RuleRepo` ports and shared rule
schemas. No schema, port, configuration or database changes. The controller composes `POST /rules:suggest`
and serializes tuples to `RuleSuggestionsOut`; this chapter's adapter/service files do not own routing.

## How to test

```bash
docker run --rm --network none \
  --mount "type=bind,src=$PWD,dst=/app,readonly" \
  feature-signal:dev pytest -q -p no:cacheprovider \
  tests/unit/test_llm.py tests/service/test_rule_suggest_service.py
```

Expected: `61 passed`. Tests use fake clients/providers and cannot access the network.
The installed OpenAI SDK also successfully converted all three private response models to strict schemas
offline. API implementation follows the [official structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs)
and [Python SDK parsing helpers](https://github.com/openai/openai-python/blob/main/helpers.md), checked
using official documentation and Context7.

## Manual smoke evidence

The controller verified the account model list on 2026-11-08: `gpt-6-luna` was available and
`gpt-6.1-luna` was absent. Local Settings selected the available model. One bounded structured-output
call through this adapter completed: 860 input tokens and 188 output tokens (69 reasoning tokens),
1,048 tokens total. It returned one validated suggestion: `hd_export_blocked_attempts`,
`count(pt_track_hd_export_blocked)`, `window_days=null`, `feature=hd_export`. Rationale:
“Tracking blocked attempts may help characterize demand for HD export.” This establishes adapter,
schema and account compatibility. The exact seven-day blocked-HD demo remains covered by offline tests;
the live call returned a count over all history. No credentials are recorded here.

## Limits / not claimed

The controller performed the live verification above. B6 implementation tests made no network calls
and read no credentials. The automated tests alone do not establish live account capability. Property
metadata must come from an authoritative caller; the catalog currently has no typed-property contract.
Only vetted complete hypothesis statements and local rationale templates are returned; arbitrary
natural language is not claimed to be fact-validated. Copy
editing is deliberately limited to top-level title/subtitle fields.

## Status

Adapter, service and suggestion route implemented and independently reviewed. The route uses real
app-scoped catalog repositories, closes the client after each request, and returns an actionable 503
when credentials are absent. Typed property metadata is injected per app through
`app.state.brain_property_allowlists`; an absent declaration permits event-only rules.
The 63 adapter/service/API tests pass, including the exact seven-day blocked-HD example and the
regression for unsupported causal/offer claims. Next: B7 insight orchestration.

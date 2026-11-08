# 17 — Approval errors and missing demo profiles

## What

Approval needs a corresponding Adapty profile for every local user whose targeting attributes change.
Loading local demo events alone does not create these profiles in a newly configured Adapty app.

## Why

The browser reproduction took 147 seconds before failing at `write_attributes`: all 4,984 local users failed.
Four sampled users returned `404 profile_does_not_exist` from Adapty. The approval response itself had valid
CORS headers. A separate regression test found that unhandled exceptions returned HTTP 500 without CORS headers,
preventing the browser from reading the actual server error.

## How it works

- CORS wraps the complete FastAPI middleware stack, including its server-error handler.
- Unexpected exceptions return the standard JSON envelope with `internal_error`; the traceback stays in server logs.
- Missing Adapty profiles produce setup guidance that survives membership aggregation and reaches the decision log.
- `scripts/seed_adapty_profiles.py` reads the synthetic dataset and creates missing profiles using the configured
  `ADAPTY_SECRET_KEY`. Before any writes it checks the key against the selected app's metadata through the
  logged-in Adapty CLI. It preserves customer IDs, platform, country, and device metadata, and also checks that
  the response app matches `ADAPTY_APP_ID`. Existing profiles are skipped on subsequent runs.
- New profiles carry `fs_demo=lumen_282506` and opt out of external analytics. The script does not replay purchases
  or create subscription entitlements. Profile creation is explicit setup, never an automatic fallback on approval.
- Activation accepts default flow A/B tests. It selects a copied flow's original active arm, an explicit `control`
  arm, or the unique other active arm when the offer is part of a two-arm test. Zero-weight arms are ignored;
  ambiguous tests produce actionable errors. Existing default audiences stay in place.
- Failed proposals can retry before test creation was attempted, preserving their logs. An existing equivalent
  active proposal prevents a duplicate test. Status/timestamp checks serialize approval and publish continuation.
- Failed proposal cards show the failed step's message and offer safe retries. An old duplicate links to its active test.

## Contract touched

No endpoint, schema, or port signature changed. Failed proposals gain a guarded retry transition; publish continuation
claims `executing` before remote mutations. HTTP 500 now follows the existing error envelope and CORS policy.
Membership error details add `causes`, a map from error code to failed-user count.

## How to test

For a new demo app, after configuring its key and downloading the Lumen dataset:

```sh
docker compose exec api python scripts/seed_adapty_profiles.py --users 5000
```

The script uses eight concurrent requests and retries rate limits and transient failures. It can be rerun after
an interruption. Both the local events and the remote profiles must use the same `lumen_282506_NNNNN` identities.
The target app also needs placement `fs_test`, with the published `Main - 3 plans` flow as its default audience.
The demo maps proposals for `main` to this placement; copying flows into a new app does not create it.

```sh
docker compose run --rm test
```

The regression tests cover readable HTTP 500 responses, rejection of unconfigured origins, missing-profile
diagnostics, idempotent profile seeding, app mismatches, and failures that must not create profiles.

## Limits

Earlier failed decisions remain in the audit history. After repairing setup, use **Retry approval** on the same
proposal. If test creation was already attempted, inspect its remote state before taking further action; automatic
retries cannot safely determine whether a timed-out create succeeded. A proposal requiring publication still waits
for a human to publish its flow in Adapty. This is an expected state, not an approval failure.

Adapty's [create-profile API](https://adapty.io/docs/api-adapty/operations/createProfile/) documents the seed request.
Starlette's [CORS middleware guidance](https://www.starlette.io/middleware/#corsmiddleware-global-enforcement)
explains why CORS needs to wrap the error handler.

## Status

Verified on 2026-11-08: 590 backend tests and 53 frontend tests pass; the production build, lint, formatting,
and task graph pass. Approval regression coverage includes plain-flow and A/B defaults, copied-flow publication,
ambiguous and disabled arms, each upstream failure step, concurrent requests, and duplicate retry protection.
The selected demo app now has 5,000 synthetic profiles and the `fs_test` placement. Playwright approved
`pr_69ad161f85` through the dashboard: all five activation steps succeeded, and A/B test
`4da42040-c49f-404c-a42f-d9bef1b8a81f` is live on `fs_test`.

The follow-up checked every current proposal against real Adapty configuration. Playwright retried both failed
onboarding offers (`pr_9db1ac0fbd`, `pr_3b49059017`) and approved the untouched published offer (`pr_6229d91a14`):
all are live. The four copied draft flows now correctly wait at `awaiting_publish`. A premature continuation
returns readable `409 flow_not_published` without changing state. The old failed `fs_test` duplicate points to
its equivalent live proposal; retry is blocked without creating another test. Read-back verified all four live
tests and their segment audiences, with onboarding's original default A/B test preserved. Full evidence is in
`output/playwright/approval-all-cases-verification.json`.

A network suspension interrupted the first verification after 4,976 successful profile writes. An equivalent
draft retained that progress and completed the remaining eight writes. Earlier failures remain in the audit log.
Screenshots and request evidence are saved in `output/playwright/approval-fix-verification.json` and
`output/playwright/approval-fixed-live.png`.

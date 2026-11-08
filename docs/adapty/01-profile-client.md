# 01 — Profile client

**Area:** C · **Branch/PR:** `adapty/profile-client` · **Date:** 2026-11-08

## What
`AdaptyProfileClient` writes custom attributes on one Adapty profile. It is the real implementation of the
`AttributeWriter` port, so everything that writes to Adapty (membership sync, activation) goes through it.

## Why
Adapty only sees what the app writes on a profile (`docs/plan.md`, "Why it is missing"). This is the single
place where we write, so the limits and the payload shape are checked once.

## How it works
1. `feature_signal/integrations/adapty/profile_client.py:AdaptyProfileClient.write(customer_user_id, attributes)`.
2. `validate_attributes` refuses a payload Adapty would reject, **before** sending: more than 30 attributes,
   a key longer than 30 characters or with characters outside letters, digits, `_`, `-`, `.`, a string value
   longer than 50, a boolean, a non-finite number. It raises `ApiError(422, "attribute_limit")`.
3. It sends `PATCH /api/v2/server-side-api/profile/` with `Authorization: Api-Key <secret>` and
   `adapty-customer-user-id`. The body is a **list**: `{"custom_attributes":[{"key":…,"value":…}]}`.
4. `None` is sent as JSON `null`, which deletes that key. PATCH merges with the other attributes.
5. 429, 500, 502, 503, 504 and network errors are retried (4 attempts, exponential delay, `Retry-After`
   honoured up to 30 s). Any other 4xx fails at once as `ApiError(502, "adapty_rejected")` with Adapty's answer.
   When retries run out: `ApiError(502, "adapty_unavailable")`. The secret never appears in an error.
6. `AdaptyProfileClient.from_settings(settings)` builds it from `core/config.py`.

## Contract touched
Port `AttributeWriter` (`docs/contracts/ports.md`), implemented unchanged. Adapty server-side API, see
`CLAUDE.md` §5.

## How to test
```bash
docker compose run --rm test
```
Expected: `42 passed` (19 of them in `tests/unit/test_adapty_profile_client.py`) and `39 tasks, 0 problems`.

Manual, on ONE test profile (never on all seed users): write a string and a number, delete a key with `None`,
read the profile back with `GET`, clean up. Done on 2026-11-08 on a test profile of the Lumen app: text and
number were written, the deleted key was gone, the other attributes were untouched.

## Limits / not claimed
- It writes; it does not read. Reading the current attributes (for "write only what changed") belongs to the
  membership sync (C9).
- The 30-attribute limit is checked on the payload only. A profile that already holds other attributes can
  still exceed 30 in total; Adapty then refuses and we surface its answer as `adapty_rejected`.
- Characters outside ASCII in a value were not tested; keep values ASCII.
- Not verified here: whether an empty string is a valid value.

## Status
Done · Next: C2 — Adapty CLI adapter

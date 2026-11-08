# 09 — Adapty webhook: real outcomes

**Area:** A · **Branch/PR:** `ingest/adapty-webhook` · **Date:** 2026-11-08

## What
`POST /v1/apps/{app_id}/adapty-webhook` receives Adapty's webhook events (purchases, renewals, refunds,
trials, cancellations) and stores them as events of the same user. The first one also creates the rule
`adapty_net_revenue_90d` — the plan's metric (purchases minus refunds, 90 days) on real Adapty data.

## Why
Measurement used to rely on the offline dataset only. With the webhook the loop closes inside Adapty:
Adapty → our history → values → decision → Adapty, and each A/B arm's net revenue can be read per user.

## How it works
`services/adapty_webhook_service.py:to_event` (format from
[webhook-event-types-and-fields](https://adapty.io/docs/webhook-event-types-and-fields) and
[set-up-webhook-integration](https://adapty.io/docs/set-up-webhook-integration)):
- `{}` (verification on Save) → `{}` with 200. Unusable body → `{}` with 200: Adapty pauses delivery after
  repeated failures, so we acknowledge everything that passed the auth check.
- Auth: Adapty sends the dashboard value as `Authorization`; compared in constant time with
  `ADAPTY_WEBHOOK_AUTH` (empty = no check, local only). Wrong → 401.
- Key `adapty_<event_type>` (renamed types slugged to our key pattern), registered with a description on
  first sight. User = `customer_user_id`, else `adapty_profile:<profile_id>`.
- `event_id` = uuid5(`profile_id` + `profile_event_id`): Adapty delivers at least once (up to 9 retries in
  24 h), our ingest counts each event once.
- Props: scalar `event_properties` only; `net_revenue_signed_usd` = +`net_revenue_usd` for
  subscription_started / renewed / trial_converted / non_subscription_purchase, − for refunds.
- Then the normal ingest path: idempotent insert, value recompute for the user, membership sync.

## Contract touched
New endpoint (`docs/contracts/api.md`, Adapty webhook), setting `ADAPTY_WEBHOOK_AUTH`, router mount.
Nothing existing changed.

## How to test
```bash
make test-docker
curl -s -XPOST localhost:8000/v1/apps/$APP/adapty-webhook -H 'content-type: application/json' -d '{}'
curl -s -XPOST localhost:8000/v1/apps/$APP/adapty-webhook -H 'content-type: application/json' \
  -d '{"profile_id":"p1","customer_user_id":"lumen_282506_00007","event_type":"subscription_started","event_datetime":"2026-11-08T01:02:03.000000+0000","event_properties":{"profile_event_id":"pe1","net_revenue_usd":8.5,"environment":"Sandbox"}}'
```
Expected: `341 passed`; `{}`, then `{"accepted":1,"duplicates":0}`; the same curl again → `duplicates: 1`.
For the real thing: Adapty dashboard → Integrations → Webhook, sandbox URL = a public tunnel to the API
(e.g. `cloudflared tunnel --url http://localhost:8000`), then buy in sandbox.

## Limits / not claimed
Not yet tried against a live Adapty webhook (needs a public URL). Sandbox and production events are both
stored; `environment` tells them apart. Renamed event types keep working but lose the revenue sign.

## Status
Done · Next: `make demo`, demo script.

# API contract (v1)

**Status: frozen for Phase 1–4.** This file is the single source of truth between the four areas.
Backend implements it, the dashboard and the SDK call it, tests assert it. A change goes through the
`contract-change` skill and is logged in [CHANGES.md](CHANGES.md). The pydantic models in
`feature_signal/schemas/` mirror this file one to one.

Conventions
- Base path `/v1`. JSON only. Times are ISO 8601 UTC strings (`2026-11-07T18:00:00Z`).
- One app per request, addressed in the path: `/v1/apps/{app_id}/...`. `app_id` is the Adapty app UUID
  (Lumen: `c6c7bdd1-1010-4343-8b29-837a77793cab`).
- `customer_user_id` is the join key with Adapty (the same id the app passes to the Adapty SDK).
  Seed users look like `lumen_282506_00007`.
- Errors: `{"error": {"code": "snake_case", "message": "human text", "details": {...}}}` with a 4xx/5xx status.
- Not implemented yet: the route exists and returns `501` with code `not_implemented`. The dashboard
  shows "coming soon" for 501 and never crashes.
- Owner column: **A** ingest & rules, **B** brain, **C** Adapty & proposals, **D** dashboard (consumer only).

## Endpoints

| Method | Path | Owner | Purpose |
|---|---|---|---|
| GET | `/v1/health` | A | `{"status":"ok"}` |
| POST | `/v1/apps/{app_id}/features` | A | Define a feature (a group of events) + which plans include it; creates its default rules |
| GET | `/v1/apps/{app_id}/features` | A | Feature list |
| POST | `/v1/apps/{app_id}/event-types` | A | Register an event type (once per type) |
| GET | `/v1/apps/{app_id}/event-types` | A | Event catalog |
| POST | `/v1/apps/{app_id}/events` | A | Ingest a batch of events (idempotent) |
| GET | `/v1/apps/{app_id}/users/{customer_user_id}/timeline` | A | Last events of one user |
| POST | `/v1/apps/{app_id}/rules` | A | Save a rule (human or accepted AI suggestion) |
| GET | `/v1/apps/{app_id}/rules` | A | List rules |
| POST | `/v1/apps/{app_id}/values:recompute` | A | Recompute all rule values for all users |
| GET | `/v1/apps/{app_id}/values` | A | Computed values per user (paged) |
| GET | `/v1/apps/{app_id}/users/{customer_user_id}/features` | A | Feature profile of one user (values grouped by feature + tier) |
| POST | `/v1/apps/{app_id}/rules:suggest` | B | LLM suggests rules from the catalog (not saved) |
| POST | `/v1/apps/{app_id}/insights:run` | B | Rank values, build segments, compute uplift |
| GET | `/v1/apps/{app_id}/insights/latest` | B | Last insight run |
| GET | `/v1/apps/{app_id}/proposals` | C | List proposals (`?status=draft`) |
| POST | `/v1/apps/{app_id}/proposals` | C | Create proposals (B calls this from an insight run) |
| PATCH | `/v1/proposals/{proposal_id}` | C | Human edit of rule values (threshold, holdout, flow) |
| POST | `/v1/proposals/{proposal_id}:approve` | C | Approve → execute in Adapty |
| POST | `/v1/proposals/{proposal_id}:reject` | C | Reject with reason |
| GET | `/v1/apps/{app_id}/decisions` | C | Decision log (who decided, what ran in Adapty) |
| GET | `/v1/apps/{app_id}/settings` | C | Mode and autopilot limits |
| PUT | `/v1/apps/{app_id}/settings` | C | Change mode |
| POST | `/v1/apps/{app_id}/lookup` | C | Which flow Adapty serves to given users (demo proof) |
| POST | `/v1/apps/{app_id}/membership:sync` | C | Fast loop: re-check tiers and segments, write only changed Adapty attributes |
| POST | `/v1/proposals/{proposal_id}/paywall-draft` | C | Copy of live flow config with changed title and plans |

## Schemas

### Feature (a group of events)
```json
{ "key": "ai_generate", "name": "AI generation",
  "description": "User generates an image from a prompt, optionally with an uploaded photo, and may regenerate",
  "plans": ["premium"], "created_at": "2026-11-07T18:00:00Z" }
```
- `key` `^[a-z][a-z0-9_]{1,21}$` (≤22 chars, because it becomes the Adapty key `f_<key>_tier`, max 30).
- How wide or narrow a feature is, is the developer's choice. `plans` = access levels / products that
  include the feature; the paywall may highlight a feature only if an offered plan is in this list.
- Creating a feature also creates its **default rules** (`source: "default"`, `feature: <key>`):
  `<key>_uses_total` (count, all history), `<key>_uses_7d` (count, 7 d), `<key>_days_active_7d`
  (days_active, 7 d), and `<key>_used_<event>` (exists) for each event in the feature. The AI suggests
  extra, composed rules on top (ratio, sums, conditions).

### EventType
```json
{ "action_id": 3, "key": "regenerate_click", "name": "Regenerate clicked",
  "description": "User asked for a new result after the first generation",
  "features": ["ai_generate"], "created_at": "2026-11-07T18:00:00Z" }
```
Create body: `key` (`^[a-z][a-z0-9_]{1,39}$`), `name`, `description` (required, 1–500 chars),
`features` (0–5 feature keys; an event may belong to several features and is counted in each).
Re-registering an existing `key` updates name/description/features and returns `200`.

### Event batch
```json
POST /v1/apps/{app_id}/events
{ "events": [
  { "event_id": "0b6f0c1e-5d1a-4c7e-9a0e-3f0f2b7c9a11",
    "customer_user_id": "lumen_282506_00007",
    "key": "bg_remove",
    "occurred_at": "2026-11-07T17:59:58Z",
    "props": { "photo_id": "p_123" },
    "decision_id": null } ] }
→ 200 { "accepted": 1, "duplicates": 0, "unknown_keys": [] }
```
- `event_id` is a client-generated UUID and the primary key: a repeated id is a duplicate, never counted twice.
- `received_at` is set by the server. Max 500 events per batch.
- Unknown `key` → the event is rejected and listed in `unknown_keys` (register the type first).
- `props` are small values: number, bool, string ≤100 chars, null; at most 20 per event. Numbers must be
  JSON numbers (`40`, not `"40"`) so rules can add them up. **Never send free text** (e.g. the prompt):
  send what is derived from it (`prompt_len: 62`). Quotas are the app's knowledge: send state such as
  `tokens_left`, not only `tokens_used`.
```json
{ "key": "generate_click", "props": { "tokens_used": 40, "tokens_left": 0, "with_upload": true } }
```

### Rule (how a value is derived from events)
```json
{ "rule_id": 7, "key": "distinct_photos_edited_7d",
  "name": "Distinct photos edited in the last 7 days",
  "description": "Counts different photo_id values across edit events in a 7-day window",
  "source": "ai",
  "definition": { "event_keys": ["bg_remove", "ai_enhance"], "measure": "distinct",
                  "distinct_prop": "photo_id", "window_days": 7 },
  "value_type": "float", "created_at": "..." }
```
| `measure` | Needs | Value |
|---|---|---|
| `count` | — | number of matching events |
| `distinct` | `distinct_prop` | number of different values of a prop |
| `exists` | — | 1 if any matching event, else 0 |
| `days_active` | — | number of different days with a matching event |
| `ratio` | `denominator_event_keys` | count(`event_keys`) / count(denominator), 0 if denominator is 0 |
| `sum` / `max` / `min` | `value_prop` | over a numeric prop |
| `last` | `value_prop` | the prop of the latest event (by `occurred_at`) |

Optional `where: {"prop", "op": eq|lt|lte|gt|gte, "value"}` keeps only matching events first.
`window_days` ∈ 1–90 or `null` (all history), always on `occurred_at`. `source` ∈ `human` | `ai` | `default`.
`feature` (optional) puts the value into that feature's profile.
Examples: regenerate rate = `{"event_keys":["regenerate_click"],"measure":"ratio","denominator_event_keys":["generate_click"],"window_days":7}`;
ran out of tokens = `{"event_keys":["generate_click","regenerate_click"],"measure":"exists","where":{"prop":"tokens_left","op":"lte","value":0},"window_days":7}`;
tokens left = `{"event_keys":["generate_click","regenerate_click"],"measure":"last","value_prop":"tokens_left"}`.

### Rule suggestion (B, not persisted)
```json
POST /v1/apps/{app_id}/rules:suggest → 200
{ "suggestions": [ { "rule": { ...Rule without rule_id... },
                     "rationale": "Processing different photos is when the product delivers value" } ],
  "model": "gpt-6-luna" }
```
Accepting a suggestion = the dashboard POSTs its `rule` to `/rules`.

### Values
```json
GET /v1/apps/{app_id}/values?rule_key=distinct_photos_edited_7d&limit=100&cursor=...
{ "items": [ { "customer_user_id": "lumen_282506_00007", "rule_key": "distinct_photos_edited_7d",
               "value": 4.0, "computed_at": "..." } ], "next_cursor": null }
```

### Feature profile (A) — the "JSON per feature", kept by us, never sent to Adapty
```json
GET /v1/apps/{app_id}/users/u_42/features
{ "customer_user_id": "u_42",
  "features": [ { "feature": "ai_generate", "name": "AI generation",
                  "values": { "ai_generate_uses_total": 14, "ai_generate_uses_7d": 9,
                              "ai_generate_days_active_7d": 4, "ai_generate_used_image_upload": 1,
                              "regenerate_rate_7d": 0.4, "tokens_used_7d": 360, "tokens_exhausted_7d": 1 },
                  "tier": "high", "computed_at": "..." } ] }
```
`tier` is set only for features whose tier passed measurement (see `tiers` in InsightRun), else `null`.

### InsightRun (B)
```json
POST /v1/apps/{app_id}/insights:run  { "source": "offline" }   // or "live"
→ 200 {
  "run_id": "ir_20261107_1800", "source": "offline", "created_at": "...",
  "rankings": [ { "feature": "ai_edits_first_day", "threshold": 5, "direction": "up",
                  "lift": 2.4, "ci_low": 2.1, "ci_high": 2.7, "holdout_lift": 2.3,
                  "n_above": 13541, "n_below": 36459, "passed": true } ],
  "segments": [ { "segment_key": "power_editor", "label": "5+ edits, no subscription",
                  "conditions": [ { "field": "ai_edits_first_day", "op": ">=", "value": 5 },
                                  { "field": "subscription_state", "op": "IN", "value": ["never_subscribed"] } ],
                  "size": 13541, "net_arpu_90d": 15.57, "ci_low": 14.9, "ci_high": 16.2 } ],
  "uplift": [ { "segment_key": "power_editor", "test": "Main: 3 plans vs lifetime anchor (NA)",
                "better_arm": "main_lifetime", "worse_arm": "main",
                "diff_net_90d": 14.40, "ci_low": 9.1, "ci_high": 19.8, "n_a": 412, "n_b": 398 } ] }
```
Also in the response:
```json
  "tiers": [ { "feature": "ai_generate", "rule_key": "ai_generate_uses_7d", "attribute": "f_ai_generate_tier",
               "low_max": 2, "mid_max": 7, "passed": true } ],
  "hypotheses": ["regenerate_rate_7d", "tokens_exhausted_7d"]
```
- `tiers`: measured cut points turning one value per feature into `low` / `mid` / `high`
  (`value <= low_max` → low, `<= mid_max` → mid, else high). Only `passed: true` tiers are written to Adapty.
- `hypotheses`: rules with no purchase outcome yet (new events). They are not ranked; they can only
  enter an A/B test, labelled "hypothesis" in the dashboard.
- `direction` ∈ `up` (offer) | `down` (reward instead of paywall).
- `passed` is true only if the holdout check and the bootstrap interval both hold.

### Proposal (C)
```json
{ "proposal_id": "pr_01", "app_id": "...", "status": "draft",
  "created_by": "ai", "decided_by": null, "mode_at_decision": null,
  "trigger_placement": "main",
  "segment_key": "power_editor",
  "condition": { "attribute": "p_segment", "op": "IN", "value": ["power_editor"] },
  "adapty_filters": [ { "field": "<no-subscription field, verified by C>", "op": "IS NULL", "value": null } ],
  "action": { "type": "flow", "flow_id": "4d8837b5-23f0-4ba3-a09f-0ba6d704ed85", "flow_name": "main_lifetime",
              "highlight_feature": "ai_generate", "needs_publish": false },
  "holdout_pct": 20, "cooldown_days": 7,
  "expected_effect": { "metric": "net_revenue_90d", "diff": 14.40, "ci_low": 9.1, "ci_high": 19.8 },
  "reason": "Users with 5+ edits gain $14.40 net from the lifetime anchor in the randomized Main test",
  "evidence": { "run_id": "ir_20261107_1800", "uplift_test": "Main: 3 plans vs lifetime anchor (NA)" },
  "edits": [ { "at": "...", "field": "holdout_pct", "from": 20, "to": 30 } ],
  "adapty": { "segment_id": null, "placement_id": null, "ab_test_id": null, "attributes_written": 0 },
  "created_at": "...", "updated_at": "..." }
```
- `status` ∈ `draft` → `approved` → `executing` → `live` | `failed`; or `draft` → `rejected`.
  With `action.needs_publish: true` (a new AI paywall, still a draft flow): `executing` → `awaiting_publish`
  → (human publishes the flow) → `live`. This holds in autopilot too.
- `adapty_filters`: fields Adapty already knows (e.g. no active subscription), ANDed with `condition` in the
  same Adapty segment. We don't copy subscription state into our attributes.
- `decided_by` ∈ `human` | `autopilot`. Every edit is appended to `edits` (a human correction is data).
- PATCH body (flat, all optional, unknown fields → 422): `{"holdout_pct": 30, "cooldown_days": 14,
  "flow_id": "...", "condition_value": ["power_editor"], "trigger_placement": "ai_limit_reached"}`.
  These map to `holdout_pct`, `cooldown_days`, `action.flow_id`, `condition.value`, `trigger_placement`.
  Never paywall JSON. Reject body: `{"reason": "..."}`.

### Settings (C)
```json
{ "mode": "human", "autopilot": { "max_live_proposals": 3, "min_holdout_pct": 10, "allow_publish_flow": false } }
```
`mode` ∈ `human` (default) | `autopilot`. In autopilot the system may write attributes, create the
segment, attach the audience and create + start the A/B test. Publishing a flow is always human, so
autopilot runs end to end only with already published flows; a new AI paywall waits in `awaiting_publish`.

### Decision log entry (C)
```json
{ "decision_id": "dc_01", "proposal_id": "pr_01", "decided_by": "human", "action": "approve",
  "steps": [ { "step": "write_attributes", "ok": true, "detail": { "profiles": 412 } },
             { "step": "segments_create", "ok": true, "detail": { "segment_id": "..." } } ],
  "at": "..." }
```

### Lookup (C, demo proof)
```json
POST /v1/apps/{app_id}/lookup { "placement": "main", "customer_user_ids": ["lumen_282506_00007", "lumen_282506_00042"] }
→ 200 { "results": [ { "customer_user_id": "lumen_282506_00007", "segment_hash": "7f21e4f3bfaed5b9",
                       "flow_id": "4d8837b5-...", "flow_name": "main_lifetime" } ] }
```

### Membership sync (C) — the fast loop
```json
POST /v1/apps/{app_id}/membership:sync { "customer_user_ids": ["u_42"] }   // null = every user with values
→ 200 { "checked": 1, "changed": 1, "attributes_written": 2 }
```
For each user: compute `f_<feature>_tier` from the passed tiers and `p_segment` from the live proposals'
conditions; PATCH only keys whose value changed (`null` when the user left). A calls the same service
after every ingest batch commits (`MembershipSync` port), so a click reaches the Adapty segment in seconds.

### Paywall draft (C, Phase 5)
```json
POST /v1/proposals/{proposal_id}/paywall-draft { "title": "Unlimited AI generation", "product_ids": ["..."],
                                                  "highlight_feature": "ai_generate" }
→ 200 { "base_flow_id": "...", "draft_flow_id": "...", "status": "draft", "changed_paths": ["screens[0].title"] }
```
Publishing stays a human click in Adapty (or `flows publish` behind an explicit confirmation).
`422 feature_not_in_plan` if `highlight_feature` is not in `plans` of any offered product: we never promise what the plan doesn't give.

## Adapty attributes we write (stable keys, never renamed)
| Key | Type | Meaning |
|---|---|---|
| `p_segment` | string | The approved group the user belongs to now (`ai_power_free`), or deleted (`null`). One per user. Our segments target this. |
| `f_<feature>_tier` | string | `low` / `mid` / `high` for each feature whose tier **passed measurement** (max 10 features). Marketers can build their own Adapty segments from these. |

At most 11 of the 30 slots; an app with 50 features uses the same. Everything else (history, profiles,
raw values) stays with us. Segment filters: `attributes__p_segment@string IN [...]`,
`attributes__f_ai_generate_tier@string IN ["high"]`, ANDed with `adapty_filters`. Time of day is not
collected (Adapty doesn't serve by hour).

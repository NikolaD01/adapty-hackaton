# 11 — Demo script, part C (about 60 seconds)

Shows: a human approves a proposal, Adapty really changes, and two users get different paywalls.
Part of the 3-minute demo (`docs/plan.md`, "Demo").

## Before (once, not on stage)
- `docker compose run --rm adapty-login` done; `docker compose up api` running (`/v1/health` is `ok`).
- `.env` has `ADAPTY_SECRET_KEY` and `ADAPTY_APP_ID`; mode is `human` (`GET /settings`).
- A draft proposal exists (from B, or created through `POST /proposals`) for a placement the team agreed to demo on.
  Never rehearse on the real placement without deciding it: starting a test cannot be undone and the CLI cannot delete segments.
- Two test users ready: one that will be in the segment, one that will not. Open the Adapty dashboard on that placement.

## On stage
| Time | Say | Do | Shows |
|---|---|---|---|
| 0–10 s | "The AI proposed this group and this paywall; nothing happens until a person decides." | Open the proposal card in our dashboard (`GET /proposals?status=draft`) | finding, rule, expected effect, holdout |
| 10–20 s | "I can edit the rule, not the paywall JSON." | Change the holdout (`PATCH`), point at the `edits` entry | edits are logged |
| 20–35 s | "Approve." | `POST /proposals/{id}:approve` (button) | status `live`; decision steps all `ok` |
| 35–50 s | "This is the real Adapty." | Switch to the Adapty dashboard: segment `[fs] <key>`, the A/B test with a control arm, the placement audience | proof we use Adapty |
| 50–60 s | "Same placement, two users, two flows." | `POST /lookup` with both users | different `segment_hash` and `flow_name` |

Lookup command:
```bash
curl -s localhost:8000/v1/apps/$APP/lookup -H 'content-type: application/json' \
  -d '{"placement":"<placement>","customer_user_ids":["<in segment>","<not in segment>"]}'
```
Note: Adapty assigns the arm at random (offer share = 100 − holdout), so a user inside the segment can still see the control
flow. The `segment_hash` always differs; if the flow name matches, run the lookup for a second in-segment user.

## If something fails
- `approve` returns `failed`: open `GET /decisions` — the failing step has `code` and `message`; say so and show the log.
- Adapty is slow: the segment change reached the profile in 0.6 s when measured; show the decision log and a pre-taken screenshot.
- Autopilot variant (only if asked): switch `PUT /settings` to `autopilot`, post a draft, it starts by itself within the limits;
  a new AI paywall waits as `awaiting_publish` for one human publish. Publishing is never automatic.

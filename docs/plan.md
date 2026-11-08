# Adapty add-on: offers based on what people do in the app
Final plan, 7 November 2026. Source of truth for the team; code follows `docs/contracts/`, rules follow `CLAUDE.md`.

## What we build
An add-on for Adapty that uses how people use the app to propose which group of users should see which
offer. The goal is that more people in that group buy a subscription, because the paywall clearly shows
what they get for what they already do in the app.
We do not build a paywall editor, a billing SDK or analytics — Adapty has all of that. We add what it lacks:
knowledge of what happens in the product before the purchase.

## Why it is missing
Adapty can show a different paywall to a different group. A group is a segment over custom attributes —
fields the app writes on the user's profile.
But Adapty doesn't collect those attributes: the app has to compute the value and send it. Adapty's
`audiences` agent skill warns developers: "A segment over an attribute nobody sets matches nobody."
We also verified that an attribute keeps only its current value, no history. If we write 7 today and 12
next week, Adapty only knows 12. The history of actions therefore has to live with us.
The demo data shows it well: Lumen profiles have `ai_edits_first_day`, already computed — as if someone had
solved the problem. Nobody did: the seed script read the number from a file. In a real app the field doesn't
exist, and someone has to decide what to count, and guess.

## What the developer tracks
Through our SDK the developer tracks the actions that matter for their app and groups them into
**features**. A feature is a group of events, as wide or narrow as the developer wants: "AI generation" =
generate click, image upload, regenerate click. Each event type has a name, a description and the
features it belongs to (one or more). Each feature says which plans include it, so a paywall never
promises what the plan doesn't give.
An event can carry small values: `{"tokens_used": 40, "tokens_left": 0, "with_upload": true}`. Numbers stay
numbers so we can add them up. Quotas are the app's knowledge, so the app sends the state (`tokens_left`)
and we read "ran out of tokens" from it. Free text such as the prompt never leaves the app; at most its
length or a category the app computes.
Descriptions are not decoration: they let us write findings in human words ("people who regularly remove
backgrounds" instead of "key bg_remove"). They don't decide what matters — measurement does.

## Our tables
Features and event catalog: written once by the developer.
Event history: append-only, one row per event: **who**, what, when it happened on the phone, when it reached
us (phones buffer offline; with one timestamp a "last 7 days" counter silently lies), its props, and its own
id, so a retried request after a timeout doesn't duplicate.
Rules for deriving values from events: a table, not code, so a rule can be added or changed without a release.
Values per user, grouped by feature into a **feature profile** (the "JSON per feature"): uses in total and in
7 days, active days, whether each event was used, plus composed values. This profile stays with us.
Because Adapty keeps no attribute history, our history is the only time axis. That is a division of labor:
they hold the current decision, we hold the path to it.

## Default values, and AI suggests what else is worth computing
When a feature is defined, it gets default values automatically: uses in total, uses in 7 days, active days
in 7 days, and "used it" for each of its events. The AI then suggests composed values on top — the first
and most important place where AI works: how many different photos a user processed in 7 days, how often
they regenerate after generating (a ratio), how many tokens they spent, whether they ran out of tokens,
whether the free plan stopped them at the full-resolution export. Nobody instruments those in advance
because nobody knows which will matter. Rule measures: count, distinct, exists, active days, ratio, sum,
last, max, min, each with an optional condition (`tokens_left <= 0`) and a time window.
The choice is then measured, not guessed. A value enters the ranking and must hold on users the model
hasn't seen; if it doesn't separate people, it is dropped. A value with no purchase data yet (a brand-new
event) is a **hypothesis**: it is not ranked, it can only go into an A/B test, and the dashboard says so.
Why this isn't left to the model: in the same data `photos_imported` sounds as reasonable as
`ai_edits_first_day` and predicts nothing ($8.73–$9.55, flat) while the other goes $3.73–$16.57. Importing is
preparation; processing is when the product delivers. Developers usually instrument the former first.

## From values to tiers and a segment
For each feature that passed measurement, its main value is cut into three **tiers** — low, mid, high — at
measured cut points (revenue must really rise from low to high). Not active/inactive: revenue rises step by
step with use, so a yes/no loses the signal. Then we combine tiers with what Adapty already knows —
subscription state, country, platform — e.g. users without a subscription with high AI generation use who
ran out of tokens. The combination carries the value: one attribute gives a 4.4× spread, four axes give 24×
across 55 narrow groups ($0.89–$21.78 per user). We propose only a few measured segments, never one per
combination of features.
What goes to Adapty is small and fixed: `f_<feature>_tier` for each passed feature (max 10, so marketers can
also build their own segments from them) and `p_segment`, the approved group the user is in now. At most
11 of the 30 attribute slots; an app with fifty features uses the same. Adapty's segment = `p_segment` AND
Adapty's own filter (e.g. no active subscription) — we don't copy subscription state.
Two speeds. Rarely: measure, propose a segment, approve, prepare the paywall, start the test. After every
event: refresh the user's profile, re-check tiers and segments, and write to Adapty only what changed. The
change reaches the Adapty segment in 0.6 s.

## The paywall for that segment
For that segment the AI prepares a paywall that highlights full-resolution export — only if the offered plan
includes it (checked against the feature's plans; we never promise what the product doesn't give). This is the second place AI works: it takes the
live paywall config, changes the title and plan list and uploads it; if it composes one itself, a validator
checks it and we fall back to the edited copy, because the upload rejects invalid configs and the demo has one try.
No discounts: we highlight what the user already does. There is no randomized discount arm in this data, so
we claim nothing about discounts.

## Human and Autopilot
Two modes, Human by default. In Human the team reviews each proposal: finding, proposed rule, what changes
on the paywall, expected effect, and approve / edit / reject. "Edit" changes rule values, never paywall JSON;
every edit is logged because a human correction is data.
In Autopilot the system starts the A/B test by itself within preset limits. It may write attributes, create
the segment, attach the audience, create the A/B test and write the paywall config. Publishing a flow stays
human — users see a published paywall immediately, and Adapty itself asks for confirmation on that command.
So autopilot runs end to end with already published flows (e.g. the lifetime-anchor flow the data
recommends); a new AI paywall waits as "awaiting publish" for one human click, then the test starts.
Every decision records who made it, human or autopilot, so we can compare them later.

## How we measure
Part of the segment sees the existing paywall, part the new one. We measure net revenue per user of both
parts, not the share who buy. The control part is a requirement, not a
loss: without it we can't tell whether the difference came from our change or from who those people are, and
once we act on findings it is the only thing that keeps measurement possible.
We measure purchases minus refunds, in the same window for both sides (90 days by default; the live demo uses 60
days, because the seed data covers about four months and 90 days leaves too few users per group). Conversion alone misleads: the weekly
plan has 6.9% refunds here. The data already contains randomized A/B arms, so we see which offer lifts which
group before our first test: the lifetime offer is worth $14.40 for users with 5+ edits and $5.36 for users
with none — the group changes which offer is better, not just how much people pay.

## What we don't claim
The limit-reached paywall earns $31.18 per user vs $6.14 on onboarding. That suggests timing matters but
doesn't prove it: users reaching the limit already have 5.42 first-day edits vs 3.34, and placement assignment
isn't random. We present it as a hint.
Adapty serves per segment, not per user. We score each person individually, but content is served to the
segment, so we don't say "per-user personalization".
The Lumen dataset is synthetic: realistic shape, relationships built in on purpose, numbers are a demo base.
We don't predict a person; we place them in a measured group.

## Adapty integration (all verified on 7 November)
Attribute write: `PATCH https://api.adapty.io/api/v2/server-side-api/profile/` with `Authorization: Api-Key`
and `adapty-customer-user-id`; the body is a list `{"custom_attributes":[{"key":"…","value":"…"}]}` (an object
returns 400 "value is not a valid list"). PATCH and POST both merge; `value: null` deletes one field. Limits:
30 attributes per profile, key ≤30 chars, value ≤50. The change reaches the segment in 0.6 s (segment_hash
changes); the SDK cache serves the old flow until the profile refreshes.
Segments: `adapty segments create`, filter `field:OPERATOR:value`; custom attributes as
`attributes__<key>@string` or `@float` (comparisons only on float; string supports IN, NOT IN, IS NULL,
IS NOT NULL); filters are ANDed.
Audiences: `adapty placements update`; each entry needs `content_type`, highest priority wins. A placement
needs ≥1 audience and a default one, so "show nothing" doesn't exist; the control is the existing paywall.
Read `placements get` and send the full list.
Flows: `flows create` → `flows config update --config-file` → `flows publish` (async: publishing → published).
An unpublished flow on an audience returns 400. A/B: `ab-tests create` then `start`; only a draft can start.
Limits: per-user paywall views are only in the S3 export; the profile has no A/B arm field, so we read
Adapty's per-arm result. Everything is reversible: deleting our fields and segment restores the app.

## Code shape
Ports and adapters; `domain/` has no I/O and holds the risky parts: `rules.py`, `ranking.py` (holdout +
bootstrap interval), `uplift.py` (randomized arms). Rules are data. Statistics decides, the LLM explains —
`domain/` cannot import integrations, so ranking physically can't call a model. The LLM touches two services:
rule suggestions and paywall config. Tests on three levels, none touching the network.

## Phases
0 repo · 1 ingest · 2 brain · 3 Adapty loop (riskiest, early) · 4 demo client + our page · 5 paywall for the
segment · 6 README, AI_LOG, demo video · 7 buffer, rehearsal, submit. If late, cut: generating configs from
scratch, our MCP server, dashboard polish. Never cut phase 3.

## Demo (3 minutes)
20 s problem + quote · 40 s clicking in the app, events arriving, the user's feature profile and tier changing live · 40 s our page (what AI suggested, what passed
the check, the resulting segment) · 60 s approve, then Adapty's real dashboard with the segment and A/B test ·
20 s the same lookup for two users returns different flows (flow name or screenshot; flows don't render in a browser).

## Not doing
Context signals (dark mode, device class) · sessions and time of day (Adapty doesn't serve per hour) ·
one Adapty attribute per raw value or JSON in an attribute (50-char limit, segments can't filter JSON) ·
storing prompt text · extra pLTV/churn models · bandits ·
decompiling other apps as a demo section · generating paywalls without the live config as a base.

## Positioning
Helium chooses between paywalls based on what the app sends; we propose what is worth sending and measure
whether it helped. Adapty Autopilot works per app, placement and country; we work per narrower behavior-derived group.

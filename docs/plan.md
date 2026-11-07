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
Through our SDK the developer tracks the actions that matter for their app. Each event type has a name and a
description, and optionally a family (background removal and background replacement are the same family).
In a photo app we track photo import, background removal, export and the attempt to export in full resolution.
The description is not decoration: it lets us write findings in human words ("people who regularly remove
backgrounds" instead of "key bg_remove"). It is not used to decide what matters — measurement decides that.

## Three tables
Event catalog: one row per event type (name, description, family), written once.
Event history: append-only. Each row carries when it happened on the phone and when it reached us (phones
buffer offline; with one timestamp a "last 7 days" counter silently lies), and its own id, so a retried
request after a timeout doesn't duplicate.
Rules for deriving values from actions: a table, not code, so a rule can be added or changed without a release.
Because Adapty keeps no attribute history, this history is the only time axis. That is a division of labor:
they hold the current decision, we hold the path to it.

## AI suggests what is worth computing
The first and most important place where AI works. From the catalog and its descriptions the AI suggests
values worth deriving: how many different photos a user processed in the last seven days, how many they
exported, whether the free plan stopped them at the full-resolution export. These are composed values, not
raw counters — distinct photos, a 7-day window, one event as a barrier rather than usage. Nobody instruments
those in advance because nobody knows which will matter.
The choice is then measured, not guessed. A suggested value enters the ranking and must hold on users the
model hasn't seen; if it doesn't separate people, it is dropped.
Why this isn't left to the model: in the same data `photos_imported` sounds as reasonable as
`ai_edits_first_day` and predicts nothing ($8.73–$9.55, flat) while the other goes $3.73–$16.57. Importing is
preparation; processing is when the product delivers. Developers usually instrument the former first.

## From values to a segment
We compute the values for each user and combine them with what Adapty already knows — subscription state,
country, platform — e.g. users without a subscription who regularly remove backgrounds and have already tried
a full-resolution export. The combination carries the value: one attribute gives a 4.4× spread, four axes give
24× across 55 narrow groups ($0.89–$21.78 per user).
Only what a segment must read goes to Adapty — a small fixed set of fields, not one per feature. An app with
fifty features writes as many fields as one with five; the rest stays with us.

## The paywall for that segment
For that segment the AI prepares a paywall that highlights full-resolution export — only if the offered plan
includes it (we never promise what the product doesn't give). This is the second place AI works: it takes the
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
Every decision records who made it, human or autopilot, so we can compare them later.

## How we measure
Part of the segment sees the existing paywall, part the new one. The control part is a requirement, not a
loss: without it we can't tell whether the difference came from our change or from who those people are, and
once we act on findings it is the only thing that keeps measurement possible.
We measure purchases minus refunds, in the same window for both sides. Conversion alone misleads: the weekly
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
20 s problem + quote · 40 s clicking in the app, events arriving · 40 s our page (what AI suggested, what passed
the check, the resulting segment) · 60 s approve, then Adapty's real dashboard with the segment and A/B test ·
20 s the same lookup for two users returns different flows (flow name or screenshot; flows don't render in a browser).

## Not doing
Context signals (dark mode, device class) · sessions and time of day · extra pLTV/churn models · bandits ·
decompiling other apps as a demo section · generating paywalls without the live config as a base.

## Positioning
Helium chooses between paywalls based on what the app sends; we propose what is worth sending and measure
whether it helped. Adapty Autopilot works per app, placement and country; we work per narrower behavior-derived group.

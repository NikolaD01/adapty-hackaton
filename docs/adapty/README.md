# docs/adapty — Adapty & Proposals (C) chapter docs

Brief: [../team/C-adapty-proposals.md](../team/C-adapty-proposals.md). Template: [../templates/chapter.md](../templates/chapter.md).

| # | Chapter | What it covers |
|---|---|---|
| 00 | [Plan](00-plan.md) | Role C implementation plan |
| 01 | [Profile client](01-profile-client.md) | Attribute writes to Adapty (list body, key and value limits) |
| 02 | [Adapty CLI adapter](02-cli.md) | Segments, placements, flows, A/B tests through the CLI |
| 03 | [Served-flow lookup](03-lookup.md) | Which flow Adapty serves to given users |
| 04 | [Proposals store](04-proposals-store.md) | Proposals, edit, reject, settings |
| 05 | [Membership sync](05-membership-sync.md) | The fast loop: tiers and `p_segment` after every event |
| 06 | [Activation on approve](06-activation.md) | Attributes → segment → A/B test, every step logged |
| 07 | [Decision log](07-decision-log.md) | Who decided what and what ran in Adapty |
| 08 | [Autopilot](08-autopilot.md) | Bounded automatic approval |
| 09 | [Paywall draft](09-paywall-draft.md) | Copy of the live flow with a new title, as a draft |
| 10 | [End-to-end probe](10-end-to-end-probe.md) | C with A, B faked |
| 11 | [Demo script, part C](11-demo-script.md) | About 60 seconds of the demo |
| 12 | [B integration probe](12-b-integration-probe.md) | Probe with B's real insight run |
| 13 | [Brain wiring](13-brain-wiring.md) | B switched on at server start |
| 14 | [Real run on Adapty](14-real-run.md) | 9,968 attributes, 3 segments, 3 A/B tests (30-day window) |
| 15 | [Event properties for AI](15-ai-property-allowlist.md) | Rule suggestions can use `edits_left` and `photo_id` |

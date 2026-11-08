# Dashboard and Lumen demo

## Behavioral Targeting workflow

The dashboard turns app events into proposals for testing offers in Adapty. Open **Behavioral Targeting** in the sidebar to work through these screens.

| Screen | What it does |
|---|---|
| **Events** | Register event types such as `ai_enhance` and connect them to app features. Check the seven-day usage count for the selected profile. |
| **Metrics** | Define values per user, such as the number of AI enhancements in the past seven days. **Suggest with AI** offers candidate rules from the catalog. **Accept** saves the chosen rule. |
| **Insights** | Select **Run insights** to see which signals separate groups by net revenue and which groups responded differently in historical randomized tests. **Offline** uses the historical dataset. **Live** tries to match app events to available outcomes. Check **Actual source** for the data the run used. |
| **Proposals** | Review the proposed audience, placement, paywall flow, estimated effect and test split. Use **Edit**, **Reject** or **Approve**. A 20% holdout gives 20% of the eligible audience the existing offer as the control. |
| **Decisions** | See who made each decision and the outcome of each activation step. The details show failures at the step where they occurred. |
| **Lookup** | Compare two customer user IDs at the same placement. Check their audiences and available A/B arms. The SDK selects the arm on the device. |
| **Lumen demo** | Trigger SDK events with actions such as **AI enhance** or **Export in full resolution**. The timeline and feature profile show what was recorded for the selected demo user. |

1. Start in **Lumen demo**. Click **AI enhance** and check that the event appears and the seven-day count increases. **Events** shows where that event is registered.
2. In **Metrics**, review the rule that counts enhancements. Save a suggested rule if it measures the behavior you want. Run **Insights**. A run with sufficient evidence and a matching published flow can create a draft proposal.
3. In **Proposals**, review the draft and its expected effect. In **Human** mode, **Approve** triggers activation in Adapty. If the proposed flow is unpublished, publish it in Adapty and then continue approval.
4. Open **Decisions** from the proposal to check the activation. In **Lookup**, enter one eligible user and one comparison user at the same placement to verify how each is routed.
5. After the test has collected results, compare net revenue per user in Adapty over the same window for both arms, with refunds deducted. The proposal's expected effect comes from prior evidence. The new test measures the effect of the current offer.

The demo uses Human mode and the Insights runtime saves proposals as drafts for review. Autopilot can launch eligible tests within its limits when configured for the activation flow. A human publishes new flows in either mode. Use the [demo script](../demo.md) for rehearsal and the [live verification notes](07-live-verification.md) for the account setup.

## Chapters

- [01 — Web scaffold and Adapty Overview](01-web-scaffold.md)
- [02 — Proposal review and controls](02-proposals.md)
- [03 — Insights and Metrics](03-insights-metrics.md)
- [04 — Lumen demo access and tracking](04-lumen-tracking.md)
- [05 — Event catalog and activity](05-event-catalog.md)
- [06 — Decisions and flow lookup](06-decisions-lookup.md)
- [07 — Live API verification](07-live-verification.md)
- [08 — Dashboard rehearsal](08-demo-rehearsal.md)
- [09 — Plain-language proposal and insight review](09-plain-language-review.md)

# 10 — Outcome window (a setting, 90 days by default)

**Area:** B (edited by C on the developer's decision, B to review) · **Date:** 2026-11-08

## What
The purchase window of the outcome metric is `window_days` (`build_outcomes`, `InsightService`, `BrainRuntime.outcome_window_days`).
Default 90, so nothing changes unless a run sets it. The demo run uses **30**.

## Why 30 for the demo
Only users whose whole window has passed are used. In the seed data 25% of users are old enough for 90 days (1255 of 5000),
74% for 30 days (3720). With 90 days B's size check (150 users per side, also on the held-out 30%) leaves no live rule standing.

## What was tried (all 5000 users loaded, B's `rank` unchanged, synthetic data)
| Window | Users with a full window | Passed |
|---|---|---|
| 90 days | 1255 | none |
| 60 days | 2490 | `ai_enhance_uses_7d` |
| 30 days | 3720 | `background_uses_7d` |
| 14 days | 4409 | `ai_enhance_uses_7d`, `background_uses_7d` |

The finding is the same in every window: `ai_enhance` and `background` lift revenue 1.6 to 2.2 times, `photo_import` does not (it
never passes). What changes with the window is only which rule clears the sample-size gate. **The window was chosen by the
developer after seeing this table, so the passing rule at 30 days must not be presented as a result found independently of that choice.**

## How it works
`window_days` (whole days, 1 to 365) sets both maturity (install + window must be before `as_of`) and the purchase range.
Refunds seen by `as_of` still remove a purchase, also after the window. Column names `net_revenue_90d`, `paid_transactions_90d`,
`refunded_transactions_90d` keep their historical names; the real window is `frame.attrs["outcome_window_days"]` and
`evidence.outcome_window_days` of every draft. The reason text of a draft says "over N days".
`expected_effect.metric` of a proposal is `net_revenue_<N>d`.

## Limits / not claimed
- A shorter window favors plans that pay up front (annual, lifetime) over weekly renewals; offers are compared on the same window.
- Average revenue per user is lower (90 days: $9.49, 30 days: $7.72 in the mature seed users).
- The live rule values are synthetic events generated from the seed (A, chapter 08), so the link between use and revenue is partly built in.
- Not renamed: `net_arpu_90d`, `diff_net_90d`, `adapty_net_revenue_90d` (the live webhook rule keeps its own 90-day sum).

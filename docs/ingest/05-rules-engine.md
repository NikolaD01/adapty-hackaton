# 05 — Rules engine and rules API

**Area:** A · **Branch/PR:** `rules/engine-and-api` · **Date:** 2026-11-08

## What
`domain/rules.py:apply(rule, events, now)` computes any rule value for one user, and `POST/GET /rules`
stores human and AI rules next to the default ones.

## Why
Rules are data, not code: the AI's suggestions (regenerate rate, tokens spent, ran out of tokens) become
values without a release (`docs/plan.md`, "Default values, and AI suggests…").

## How it works
`apply` (pure): pick events whose key is in `event_keys`, inside the window (`occurred_at >= now - window_days`,
inclusive; never `received_at`) and matching `where`; then:

| measure | value |
|---|---|
| `count` / `exists` | number of events / 1 or 0 |
| `distinct` | different values of `props[distinct_prop]` |
| `days_active` | different UTC dates |
| `ratio` | count / count of `denominator_event_keys` (same window and `where`), 0 if denominator is 0 |
| `sum` `max` `min` `last` | over numeric `props[value_prop]`; `last` = latest `occurred_at` |

Numbers are int/float only (bools and numeric strings are skipped). `where` `eq` compares numbers by value
(`0 == 0.0`) and other types strictly (`True != 1`); `lt/lte/gt/gte` need numbers. Missing prop → no match.
No matching events → 0 for every measure.
`services/rule_service.py:RuleService.save` refuses unknown event keys (incl. the denominator) →
`422 unknown_event_key`, and an unknown `feature` → `422 unknown_feature`. Same key = update.

## Contract touched
`POST/GET /v1/apps/{app_id}/rules` (`docs/contracts/api.md`, Rule). No change.

## How to test
```bash
make test-docker
curl -s -XPOST localhost:8000/v1/apps/$APP/rules -H 'content-type: application/json' -d '{"key":"tokens_exhausted_7d","name":"Ran out of tokens","description":"tokens_left <= 0 in 7 days","source":"ai","feature":"ai_generate","definition":{"event_keys":["generate_click"],"measure":"exists","where":{"prop":"tokens_left","op":"lte","value":0},"window_days":7}}'
```
Expected: `77 passed`; the curl returns the rule with a `rule_id`.

## Limits / not claimed
Values are computed in chapter 6 (A7, `values:recompute`). Future-dated events (phone clock ahead) are counted.

## Status
Done · Next: A7 values, feature profile and TierStore.

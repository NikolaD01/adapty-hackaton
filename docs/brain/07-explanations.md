# 07 — Explanations of measured evidence

**Area:** B · **Branch:** `feat/segment-b-brain` · **Date:** 2026-11-08

## What
Attach readable measured evidence and explicitly tentative hypotheses to proposal reasons.

## Why
A person approving a proposal needs to distinguish randomized effects from behavioral explanations.

## How it works
The insight service writes the effect, interval, experiment, refund denominators and synthetic provenance
from numerical results. Optional explanation calls pass through `RuleSuggestService`, preserving the
repository's LLM boundary. Generated summaries and confidence cannot replace measured facts. Only a
small explicit set of tentative hypothesis statements is accepted; arbitrary causal/offer claims fall
back to deterministic text. Hypothesis confidence is zero because it is not statistically calibrated.

## Contract touched
None. Existing `Explanation` and proposal reason fields are used. The model never chooses thresholds,
tiers, randomized winners, prices or discounts.

## How to test
```bash
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev pytest -q -p no:cacheprovider tests/service/test_insight_explanations.py tests/unit/test_llm.py tests/service/test_rule_suggest_service.py
```
The comparative service tests vary generated text and simulate provider failure, then assert identical
rankings, tiers, uplift, flow choice and all draft fields except the reason. Unsupported claims are absent.

## Limits / not claimed
This is constrained explanation selection, not validation of arbitrary natural-language factual claims.
The numerical bootstrap interval is distinct from the model's discarded confidence. A manual
`gpt-6-luna` explanation call also completed with parsed structured output: 312 input and 203 output
tokens (515 total). It selected the tentative selection/unmeasured-factors hypothesis; local confidence
remained zero. Automated explanation tests use fakes. B6 records model-list verification and rule generation.

## Status
Implemented and tested, including the independent-review regression for unsupported causal/offer prose.

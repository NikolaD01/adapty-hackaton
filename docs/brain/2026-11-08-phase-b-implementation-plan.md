# Phase B — Brain Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this checklist task by task. Use subagents only when explicitly requested. Checkboxes track implementation work, not work completed while writing this plan.

**Goal:** Implement the existing Brain assignment, B1–B8, without expanding its scope or changing the agreed contracts.

**Architecture:** Follow the repository's ports-and-adapters design. Pure domain code ranks values, derives tiers and segments, and compares randomized offers. Services consume A's ports and pass proposal drafts to C; the LLM proposes rule definitions and writes explanations.

**Tech Stack:** The existing Python 3.10+, FastAPI, Pydantic v2, pandas, scikit-learn, OpenAI SDK, pytest/pytest-asyncio, and Ruff stack. No added framework.

**Spec:** [Product plan](../plan.md), [B brief](../team/B-brain.md), [B1–B8 task definitions](../tasks/B.json), [API contract](../contracts/api.md), [ports](../contracts/ports.md), and [repository rules](../../CLAUDE.md).

**Branch:** `feat/segment-b-brain`, created from current `main` at `7ace904` on 2026-11-08.

**Authority:** This is an execution checklist for those existing documents. It does not replace them, change their acceptance criteria, or approve a contract change. Where they disagree, record the discrepancy and resolve it with the owner before implementing that boundary. Suggested private function names below are implementation details, not new shared interfaces.

## Global constraints

- "ranking finds WHO IS DIFFERENT, randomized arms decide WHAT TO SHOW THEM".
- "Metric: **net revenue in 90 days** (refunds subtracted, same window for both arms). Never conversion alone."
- Domain functions have no I/O; services do not import FastAPI; external dependencies are injected through ports.
- Follow the brief's 70/30 split, fixed seed, 90% bootstrap interval, approximately 400 resamples, and minimum group size of 150 per side. Do not silently strengthen or weaken these requirements.
- At most 10 passed feature tiers and 5 segment candidates. Keep `tiers` and `hypotheses` in the agreed InsightRun shape.
- C writes `p_segment` and `f_<feature>_tier`; B does not write Adapty attributes or implement membership synchronization.
- Suggestions use the contracted measures, declared events, typed properties, and optional `where` conditions. Never collect prompts/free text.
- No automated test accesses the network. The single real LLM verification is a separate manual step.
- Settings are the only source of configuration/secrets. Verify the configured model; do not hard-code its name.
- Edit B-owned code/tests/docs only. Shared models, schemas, ports, configuration, or application wiring require the existing contract-change workflow.
- Keep code and repository text in English. Use small conventional commits on the user-requested branch. This planning task does not push, merge, or implement features.

## What was reviewed and what changed on main

Read all tracked repository Markdown documentation, all role/shared task definitions, all six task-change notices, repository workflow skills, CI/Docker configuration, and the code contracts/fakes. The linked external flow diagram could not be retrieved; the written repository documents were read.

The main update adds features, event-to-feature membership, typed properties, ratio/numeric rule measures, `where`, measured tiers, hypotheses, native Adapty filters, and the membership loop. The plan below follows those additions. The old `p_tier`, `p_top_feature`, `p_top_feature_count`, and `p_score` fields are no longer part of our output.

B's three routes are still 501 stubs. The task graph has B1 and B6 ready; other B tasks retain their existing dependencies. A and C can be faked at contract boundaries until their implementations land.

Baseline: **23 tests passed**, Ruff lint passed, **68 files passed formatting**, and the task graph reported **39 tasks, 0 problems**. Compose could not allocate a network because this host's Docker address pools are exhausted. The existing image built with host networking, and all checks passed in standalone containers with networking disabled. No infrastructure settings were changed.

## Execution order

| Existing task | Work | Dependencies and consumers |
|---|---|---|
| B1 | Offline loader and 90-day outcome | Ready; feeds B2/B4 |
| B2 | Ranking, tiers, hypotheses | B1; A7 contract/fake; feeds B3/B5/C9 |
| B3 | Segment candidates | B2; feeds B4 and C's activation |
| B4 | Uplift from randomized arms | B1/B3; feeds B5 |
| B5 | Insights API and proposal drafts | B2/B3/B4; C3 contract/fake; feeds C/D |
| B6 | LLM provider and rule suggestions | Ready on A2/A6 contracts/fakes; feeds D3/C8 |
| B7 | Explanations | B5/B6 |
| B8 | Live mode | A7/A8/B5 hard dependencies |

Follow B1 → B2 → B3 → B4 → B5, then B7/B8 when dependencies are available. B6 may be implemented earlier because it is already ready and supports D's agreed blocked-HD-export demo. This changes no task dependency or scope.

## B1 — Offline loader and 90-day net outcome

**Files:** `scripts/train_from_offline.py`; an offline adapter in new B-owned `feature_signal/integrations/offline.py`; `tests/unit/test_insight_offline.py`; `docs/brain/01-offline-outcomes.md`.

**Interfaces:** The documented `OfflineDataset.users() -> DataFrame` and `.transactions() -> DataFrame`. A private pure helper `build_outcomes(users, transactions, *, as_of)` returns one row per mature user, including users with zero purchases. Later B tasks consume this frame.

- [x] Write the five-row outcome fixture before implementation. Cover a valid purchase, no purchase, refund, purchase at/after day 90, and a user without a complete window.

```python
import pandas as pd
from feature_signal.integrations.offline import build_outcomes


def test_outcome_excludes_refunds_and_late_purchases():
    users = pd.DataFrame(
        {
            "user_id": ["paid", "zero", "refund", "late", "young"],
            "install_at": ["2026-01-01T00:00:00Z"] * 4 + ["2026-04-01T00:00:00Z"],
        }
    )
    transactions = pd.DataFrame(
        {
            "user_id": ["paid", "refund", "late", "young"],
            "purchased_at": [
                "2026-01-02T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-04-01T00:00:00Z",
                "2026-04-02T00:00:00Z",
            ],
            "price_usd": [10, 8, 20, 50],
            "refunded_at": [None, "2026-01-03T00:00:00Z", None, None],
        }
    )
    outcome = build_outcomes(users, transactions, as_of="2026-05-01T00:00:00Z")
    assert outcome.set_index("user_id").net_revenue_90d.to_dict() == {
        "paid": 10,
        "zero": 0,
        "refund": 0,
        "late": 0,
    }
```

- [x] Run `pytest -q tests/unit/test_insight_offline.py`; confirm failure before implementing the loader.
- [x] Read the two compressed CSV files; parse UTC dates and numeric values, retaining user IDs as join keys. Reject invalid or duplicate join keys rather than multiplying transactions.
- [x] Sum non-refunded `price_usd` for purchases from install until strictly before install + 90 days. Keep only fully observed users and retain zero-purchase users with outcome zero. Use an explicit dataset observation cutoff, not today's clock.
- [x] Make the CLI print user count and mean outcome. Use `Settings.offline_data_dir` and permit explicit path/cutoff arguments for reproducibility. Record the cutoff and source hashes with the output.
- [x] Run fixture tests and the local offline dataset. Document the observation-window discrepancy noted below without changing the metric.
- [x] Commit the tested loader and chapter as `feat(brain): load offline revenue outcomes`. B1 completes when the brief's fixture and printed dataset summary are verified.

## B2 — Ranking, measured tiers, and hypotheses

**Files:** `feature_signal/domain/ranking.py`; `tests/unit/test_ranking.py`; `tests/unit/test_ranking_tiers.py`; CLI reporting; `docs/brain/02-ranking-and-tiers.md`.

**Interfaces:** `rank(matrix: FeatureMatrix, outcome) -> list[Ranking]`; private tier helper returning existing `FeatureTier` objects. Services persist them through the existing `TierStore.put_many` port. `Ranking.feature` remains the numeric column/rule key; `FeatureTier.feature` is the developer-defined feature key.

- [x] Write deterministic strong-signal, hand-calculated threshold, and fixed noise fixtures. Example expected behavior:

```python
from feature_signal.domain.models import FeatureMatrix
from feature_signal.domain.ranking import rank


def test_ranking_finds_known_lift():
    users = [f"u{i:04d}" for i in range(2000)]
    matrix = FeatureMatrix(users, ["edits"], [[float(i >= 1000)] for i in range(2000)])
    outcome = {u: (10.0 if i >= 1000 else 2.0) for i, u in enumerate(users)}
    result = rank(matrix, outcome)[0]
    assert result.passed
    assert result.lift == 5.0
    assert result.holdout_lift == 5.0
```

- [x] Run `pytest -q tests/unit/test_ranking.py tests/unit/test_ranking_tiers.py`; confirm the new behavior fails before implementation.
- [x] Align outcomes by user ID. Split users 70/30 with a fixed seed; choose each numeric feature's threshold only on training data. Compute lift/direction, bootstrap 90% interval with approximately 400 resamples, and holdout lift at the unchanged threshold. Apply the brief's minimum group size and pass rule exactly; document which sample each field describes.

```python
passed = (ci_low > 1 and holdout_lift > 1) if direction == "up" else (ci_high < 1 and holdout_lift < 1)
```

- [x] Handle constant columns, missing values/outcomes, and zero denominators without emitting NaN or infinity. Keep a deterministic result for repeated runs. Do not give named demo features special treatment.
- [x] For each feature choose its best passing value. Start tier cuts from the ranking threshold and value tertiles as specified; retain them only when net ARPU rises low < mid < high and low/high CIs do not overlap. Respect existing `FeatureTier.tier` boundaries and the 10-feature cap.
- [x] List rules without joinable purchase outcomes in `hypotheses`; never rank or tier them. Keep I/O out of `ranking.py`; B5 performs tier storage.
- [x] Test up/down effects, hand-computed thresholds, seeded noise, interval behavior, unchanged threshold when holdout data changes, tier boundaries, failed tier separation, feature cap, and hypothesis exclusion.
- [x] Replay the dataset: report the actual results for `ai_edits_first_day` and `photos_imported`. The agreed target remains that the first passes and the second fails. Investigate discrepancies rather than tune to feature names.
- [x] Commit `feat(brain): rank values and derive measured tiers`; complete B2 after its tests and dataset check pass.

## B3 — Segment candidates

**Files:** Pure segment helpers in `feature_signal/domain/ranking.py` initially; `tests/unit/test_ranking_segments.py`; `docs/brain/03-segments.md`. Split into another B-owned pure module only if implementation size warrants it.

**Interfaces:** `build_segments(frame, tiers) -> list[SegmentCandidate]`, using the existing `Condition` and `SegmentCandidate` types. Pass definitions to B4/B5; C owns interpreting them for activation/membership.

- [x] Write tests for stable keys, at most five candidates, correct cohort size, net ARPU/CI, and absent metadata. Use a private `segment_key(conditions)` helper with this invariant:

```python
from feature_signal.domain.models import Condition
from feature_signal.domain.ranking import segment_key


def test_segment_key_is_stable_when_conditions_are_reordered():
    conditions = [Condition("edits_7d", ">", 7), Condition("platform", "IN", ["iOS"])]
    assert segment_key(conditions) == segment_key(list(reversed(conditions)))
    assert len(segment_key(conditions)) <= 50
```

- [x] Run `pytest -q tests/unit/test_ranking_segments.py`; confirm failure before implementation.
- [x] Combine passed feature tiers with available Adapty-known fields as the brief specifies. Do not derive subscription state from future purchase outcomes or invent missing country-tier data.
- [x] Produce no more than five interpretable segment candidates with conditions, size, mean 90-day net revenue, and CI. Use deterministic condition ordering and stable slugs; avoid run-specific IDs for `segment_key`.
- [x] Keep our behavioral conditions and native Adapty filters distinct. Resolve the existing `condition` ambiguity with C before building the shared handoff; do not choose a new wire format in this branch.
- [x] Test repeated runs, reordered users, exact tier boundaries, empty/no-passed input, missing metadata, and the segment cap.
- [x] Commit `feat(brain): build measured segment candidates`; document examples for C/D and complete B3 against the original acceptance criteria.

## B4 — Uplift from randomized arms

**Files:** `feature_signal/domain/uplift.py`; `tests/unit/test_uplift.py`; CLI reporting; `docs/brain/04-uplift.md`.

**Interfaces:** `by_segment(frame, segments) -> list[Uplift]` as documented; private `compare_arms(control, treatment)` computes difference and interval. Preserve existing shared fields.

- [x] Write known-difference, sign, and interval fixtures:

```python
import pytest
from feature_signal.domain.uplift import compare_arms


def test_uplift_sign_and_size():
    assert compare_arms([2.0] * 100, [5.0] * 100) == pytest.approx((3.0, 3.0, 3.0))
    assert compare_arms([5.0] * 100, [2.0] * 100) == pytest.approx((-3.0, -3.0, -3.0))
```

- [x] Run `pytest -q tests/unit/test_uplift.py`; confirm failure before implementation.
- [x] Within each segment and documented randomized `ab_test`, compare flow arms using the B1 90-day outcome. Never treat placement assignment as randomized or pool unrelated experiments.
- [x] Bootstrap users within each arm and report the mean difference and 90% CI. Recommend an arm only when the interval lies entirely on one side of zero. Keep winner orientation, interval signs, and arm counts consistent.
- [x] Compute and report refund counts/rates with explicit denominators alongside uplift. Agree with D how to expose them through the existing contract; any schema addition uses contract-change.
- [x] Test equal arms, positive/negative effects, missing arms, refund/late-purchase exclusions, and a seeded noisy fixture whose interval contains the known true difference.
- [x] Reproduce the brief's +$14.40/+ $5.36 reference checks and separately verify their observation window. These acceptance checks remain unresolved if the fixed-90-day results disagree; do not change their meaning or declare B4 done silently.
- [x] Commit `feat(brain): estimate randomized offer uplift` once the tests and reviewed reference calculation agree.

## B5 — Insights API and proposal drafts

**Files:** `feature_signal/services/insight_service.py`; B's `feature_signal/api/v1/insights.py`; `tests/service/test_insight_service.py`; `tests/integration/test_insight_api.py`; `docs/brain/05-insights-api.md`.

**Interfaces:** `InsightService.run(app_id, source)` and `.latest(app_id)` produce data matching `InsightRunOut`. Inject the existing dataset/value/tier/catalog/rule ports and `ProposalSink`. The Python `ProposalSink.create_many` currently returns proposal IDs; follow the actual protocol rather than the outdated prose return type.

- [x] Write fake-port service tests and dependency-overridden API tests. Start with the agreed request and response:

```python
# In a TestClient test with a fake-backed InsightService dependency:
response = client.post(f"/v1/apps/{app_id}/insights:run", json={"source": "offline"})
assert response.status_code == 200
body = response.json()
assert {"rankings", "segments", "uplift", "tiers", "hypotheses"} <= body.keys()
assert client.get(f"/v1/apps/{app_id}/insights/latest").json()["run_id"] == body["run_id"]
assert fake_sink.created
```

- [x] Run `pytest -q tests/service/test_insight_service.py tests/integration/test_insight_api.py`; the current 501 routes should fail these behavior assertions.
- [x] Orchestrate B1–B4, persist measured tiers through `TierStore`, and build proposal drafts with segment/condition, native filters, published better-arm flow, highlighted feature, effect/CI, evidence, and reason. Keep numerical work out of route handlers and network calls out of domain functions.
- [x] Pass drafts through `ProposalSink.create_many`; B does not implement proposal storage or approval. Use app-specific verified flow IDs, not offline flow names as IDs.
- [x] Preserve the brief's hypothesis behavior: label a hypothesis explicitly and never fabricate a measured effect or CI. If a hypothesis draft is built, use the documented zero-valued fields with an explanatory note; do not select an offer without an explicit experimental basis.
- [x] Implement `POST /insights:run` and `GET /insights/latest` using existing response models. Store/retrieve the latest run per app. Document the chosen demo storage lifetime; coordinate new durable tables with A if required.
- [x] Wire dependencies in B's route module where possible. Shared application composition changes remain a separate contract-change; do not leave tests as the only working construction path and claim end-to-end completion.
- [x] Test source validation, schema output, app isolation, empty/no-signal runs, sink failure, correct tier persistence, and latest-run behavior. Verify a real run creates proposals visible at C's endpoint when C3 is available.
- [x] Commit `feat(brain): expose insights and proposal drafts`; complete B5 only when the agreed handoff is demonstrated.

## B6 — LLM provider and rule suggestions

**Files:** `feature_signal/integrations/llm/{provider,prompts,schemas}.py`; `feature_signal/services/rule_suggest_service.py`; the B-owned suggestion route in `api/v1/insights.py`; `tests/unit/test_llm.py`; `tests/service/test_rule_suggest_service.py`; `docs/brain/06-rule-suggestions.md`.

**Interfaces:** Keep shared `LLMProvider.suggest_rules(catalog)`, `.explain(ranking, catalog)`, and `.paywall_copy(segment_label, base_config)` signatures. Consume A's catalog and feature definitions; agree on how feature/property context reaches the adapter without quietly changing the port.

- [x] Write fake-provider tests for valid and invalid suggestions, including the agreed first demo:

```python
from feature_signal.schemas.rules import RuleIn


def test_blocked_hd_rule_matches_the_agreed_demo():
    rule = RuleIn.model_validate(
        {
            "key": "hd_blocked_7d",
            "name": "HD export blocked",
            "description": "HD export was blocked in the last seven days",
            "source": "ai",
            "feature": "hd_export",
            "definition": {"event_keys": ["pt_track_hd_export_blocked"], "measure": "exists", "window_days": 7},
        }
    )
    assert rule.definition.measure == "exists"
```

- [x] Run `pytest -q tests/unit/test_llm.py tests/service/test_rule_suggest_service.py`; ensure missing adapter/service behavior fails before implementation.
- [x] Build prompts from features, their events/descriptions, existing defaults, and the contract's measure table. Suggest composed rules: ratio, numeric sum/last, and quota conditions such as `tokens_left <= 0`. Do not invent event/property names or suggest free-text rules.
- [x] Use structured output and Pydantic validation, then validate catalog references and measure-specific inputs. Structured JSON alone does not establish semantic validity. Reject malformed outputs with no suggestion rather than crashing.
- [x] Implement the OpenAI adapter with the configured model and injected client; keep all network behavior outside services/domain tests. Handle provider failures/refusals with the brief's safe fallback. Do not save a suggested rule automatically; D accepts it through A's rules endpoint.
- [x] Return `RuleSuggestionsOut` from `POST /rules:suggest`. Implement the provider's explanation and paywall-copy methods needed by B7/C8; C still owns paywall configuration edits, entitlement checks, and publication.
- [x] Verify the model ID via `/v1/models` before the first real call, then make one bounded structured-output call and record its result in the chapter without secrets. A listed model still needs the smoke call to establish the requested capability.
- [x] Test invalid schema, unknown catalog references, missing ratio/numeric inputs, no automatic persistence, provider failure, and the blocked-HD demo rule. Commit `feat(brain): suggest validated composed rules`.

Implementation references checked: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [model listing](https://developers.openai.com/api/reference/resources/models/methods/list), and [FastAPI dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/). These inform implementation details; they do not change the project design.

## B7 — Explanations on insights

**Files:** B's rule-suggestion/insight services and LLM prompts; `tests/service/test_insight_explanations.py`; `docs/brain/07-explanations.md`.

**Interfaces:** `LLMProvider.explain(ranking, catalog) -> Explanation`; attach readable text to proposal reason. Keep the model invocation within `rule_suggest_service` so the original two-service LLM boundary is preserved.

- [x] Write a fake-model test showing the proposed arm, threshold, effect, and CI do not change when explanation text changes:

```python
# Compare drafts from identical fake-backed runs, varying only the explanation:
assert explained.flow_id == baseline.flow_id
assert explained.expected_diff == baseline.expected_diff
assert (explained.ci_low, explained.ci_high) == (baseline.ci_low, baseline.ci_high)
assert explained.reason
```

- [x] Run `pytest -q tests/service/test_insight_explanations.py`; confirm failure before attaching explanations.
- [x] Build readable reasons using catalog labels and measured facts. Keep thresholds, tiers, rankings, and offer choice outside the model's authority. Model confidence must not be presented as a statistical interval.
- [x] Retain a deterministic factual reason if the model fails or produces unsupported claims. Clearly distinguish hypotheses from measured outcomes.
- [x] Test the fake provider, fallback behavior, and unchanged statistical fields; commit `feat(brain): explain measured proposal evidence`.

## B8 — Live mode on ValueStore matrix

**Files:** `feature_signal/services/insight_service.py`; B API tests; `tests/service/test_insight_live.py`; `docs/brain/08-live-insights.md`.

**Interfaces:** `source="live"` consumes `ValueStore.matrix(app_id)` and joins outcomes only where legitimately available. Preserve the existing response shape and the hard dependencies on A7/A8/B5.

- [x] Write tests for live matrix use, outcome alignment by ID, missing outcomes, and synthetic provenance. Example service assertions:

```python
# The service is built with a recording fake ValueStore and known outcome fixture:
run = await service.run(app_id, source="live")
assert value_store.requested_apps == [app_id]
assert run.source == "live"
assert "hd_blocked_7d" in run.hypotheses
assert all(r.feature != "hd_blocked_7d" for r in run.rankings)
```

- [x] Run `pytest -q tests/service/test_insight_live.py`; confirm the unimplemented path fails.
- [x] Read A's matrix and join verified historical seed IDs to offline outcomes where appropriate. Keep new/live-only values as hypotheses. Do not equate differently defined features merely because their names are similar.
- [x] Follow the brief's offline fallback when live outcomes are insufficient, keeping the source of evidence explicit. Do not describe an offline result as measured live evidence. Label synthetic demo-derived results as specified; coordinate the display with D using the contract workflow if additional fields are needed.
- [x] Test unknown IDs, mismatched windows, reordered rows, zero outcomes, too-small cohorts, and a large synthetic fixture with a genuine signal. Do not lower B2's minimum group size to make the 200-user demo pass.
- [x] After A7/A8 land, run the endpoint against the real value port and inspect the demo-user results. C independently owns the post-event membership loop and Adapty lookup.
- [x] Resolve the demo sample-size acceptance note below before declaring B8 complete; commit `feat(brain): connect live values to insight analysis`.

## Review notes — existing ambiguities, not approved plan changes

These notes preserve issues already found while reading the documentation and data. They do not authorize alternative requirements. Independent B work can proceed on fixtures while the relevant handoff is clarified.

1. **Uplift reference window:** The brief requires +$14.40 for 5+ edits and +$5.36 for zero edits while requiring mature fixed-90-day outcomes. The prior exploratory CSV calculation reproduced approximately +$14.39/+ $5.41 using all users and available history, but +$4.55/+ $5.13 on 12,452 mature users with a fixed 90-day outcome. The assumed cutoff was the maximum `install_at`, `2026-11-02T22:45:23Z`; its status as the export cutoff still needs confirmation. Keep the original acceptance pending review rather than replacing it.
2. **Membership condition:** B3 describes an evaluable rule over our values, while B5/API examples use `p_segment IN [...]`. C needs the former to decide which `p_segment` to assign. Confirm the intended contract with C before implementing the handoff; do not introduce a new condition format unilaterally.
3. **Offline/live equivalence:** `ai_edits_first_day` is not automatically a rolling seven-day usage rule. Confirm the intended mapping with A before making offline cut points drive live tiers.
4. **Live demo size:** A8 seeds roughly 200 users, while B2 requires 150 per side. B8's expected live rankings need clarification without weakening B2 or fabricating outcomes. Missing outcome coverage remains a hypothesis as already specified.
5. **Missing context in current ports/shapes:** The event catalog lacks property-type metadata; the LLM port accepts only the catalog; `UpliftOut` lacks refund/provenance fields; application composition and verified flow-ID mappings are not implemented. Confirm the narrowest existing-contract path with A/C/D, then use contract-change only for changes actually needed.

Local offline data is available at `../adapty-seed-data-hack/data/offline/` (50,000 users, 29,794 transactions). The seed README explains that the first 5,000 offline users map to replayed historical profiles. Newly installed `L`-prefixed copies must not be mistaken for mature users. Preserve source/window provenance in reproduction notes.

## Execution resolutions — 2026-11-08

- The developer explicitly retained the fixed 90-day metric and accepted documentation of the old benchmark mismatch; see chapter 04.
- C's actual remote code and an isolated B→C test confirm behavioral predicates belong in `evidence.segment_conditions`; native filters remain separate. Three proposals persisted and were returned by C's API.
- A8 now defaults to 1000 users. Its seed JSON provides relative-clock outcomes: 258 mature users. The real replay returns 17 live rankings with zero passing tiers under the unchanged minimum.
- Live identity and measurement eligibility are explicit; current-only rules remain hypotheses. The JSON adapter uses an arithmetic anchor without inventing an export date.
- B1–B8 code is implemented and reviewed. Production application composition and activation remain C/D integration work; no shared schema or production fake was introduced.

## Verification and chapter completion

Use the existing repository workflow after each implemented task: focused tests, whole backend checks at chapter completion, chapter documentation, B-only task/status updates, and impact review. Do not mark tasks complete during planning.

For this host, the verified test fallback is:

```bash
docker build --network=host -t feature-signal:dev .
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev pytest -q -p no:cacheprovider
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev ruff check --no-cache .
docker run --rm --network none --mount "type=bind,src=$PWD,dst=/app,readonly" feature-signal:dev ruff format --check --no-cache .
python3 tools/tasks.py check
```

Replace the container's final command with a focused pytest command when working on one task. Mount the offline dataset read-only for the manual CLI replay. Normal `make test-docker` remains the team workflow on hosts with an available Compose network.

Before handoff:

- [x] Verify all implemented B requirements with the tests above and the actual offline replay; separately record the real LLM call if completed.
- [x] Update only B's row in `docs/STATUS.md` and B's task file. Add new B-produced paths where needed. Keep other roles' task files untouched.
- [x] Read new task notices, run affected tests, then acknowledge them. Flag changed shared outputs only when an implemented change or confirmed discrepancy requires it; tell the developer which roles need review.
- [x] Run `python3 tools/tasks.py impact --diff origin/main --depth 1`, `python3 tools/tasks.py check`, and `git diff --check`.
- [x] Report what is implemented, what ran against fakes, what was verified with real integrations, and what remains pending. Leave the work on `feat/segment-b-brain` unless the developer requests integration.

## Scope check

This checklist covers the existing B1–B8 tasks. It adds no new product feature, changes no statistical acceptance threshold, and assigns no A/C/D implementation to B. The numerical and contract review notes are recorded separately from the execution steps. The original product plan, briefs, task graph, and contracts remain authoritative.

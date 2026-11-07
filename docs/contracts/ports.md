# Ports and domain models

Code twin: `feature_signal/domain/ports.py` and `feature_signal/domain/models.py`. Services receive
ports in their constructor; tests pass fakes. Changing a signature = `contract-change` skill.

| Port | Implemented by | Used by | Signature |
|---|---|---|---|
| `EventTypeRepo` | A | A, B | `upsert(app_id, EventTypeIn) -> EventType` · `list(app_id) -> list[EventType]` |
| `EventSink` | A | A | `record_batch(app_id, events) -> BatchResult` (idempotent on `event_id`) |
| `EventReader` | A | A | `history(app_id, customer_user_id, since) -> list[Event]` · `users(app_id) -> list[str]` |
| `RuleRepo` | A | A, B | `save(app_id, RuleIn) -> Rule` · `list(app_id) -> list[Rule]` |
| `ValueStore` | A | A, B, C | `put_many(app_id, rule_key, {cuid: value})` · `matrix(app_id) -> FeatureMatrix` |
| `OfflineDataset` | B | B | `users() -> DataFrame` · `transactions() -> DataFrame` |
| `FeatureRanker` | B | B | `rank(matrix, outcome) -> list[Ranking]` (pure, in `domain/ranking.py`) |
| `UpliftEstimator` | B | B | `by_segment(df, segments) -> list[Uplift]` (pure, in `domain/uplift.py`) |
| `LLMProvider` | B | B, C | `suggest_rules(catalog) -> list[RuleSuggestion]` · `explain(ranking, catalog) -> Explanation` · `paywall_copy(segment, base_config) -> dict` |
| `ProposalSink` | C | B | `create_many(app_id, list[ProposalDraft]) -> list[Proposal]` |
| `AttributeWriter` | C | C | `write(customer_user_id, dict[str, str|float|None]) -> None` |
| `AdaptyCli` | C | C | `segments_create(...)`, `placements_get/update(...)`, `ab_tests_create/start(...)`, `flows_*` |
| `FlowLookup` | C | C | `served(customer_user_id, placement) -> ServedFlow` |

Domain models (dataclasses, frozen): `EventType`, `Event`, `BatchResult`, `Rule`, `RuleDefinition`,
`FeatureMatrix`, `Ranking`, `SegmentCandidate`, `Condition`, `Uplift`, `ProposalDraft`, `Proposal`,
`Explanation`, `ServedFlow`. Fields follow `docs/contracts/api.md`.

"""Brain orchestration: numerical decisions, app-scoped storage, and proposal handoff."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

import pandas as pd

from feature_signal.domain.models import Condition, FeatureMatrix, ProposalDraft
from feature_signal.domain.ports import ProposalSink, RuleRepo, TierStore, ValueStore
from feature_signal.domain.ranking import build_segments, derive_tiers, hypotheses, rank
from feature_signal.domain.uplift import RANDOMIZED_TESTS, by_segment, refund_diagnostics
from feature_signal.integrations.offline import build_outcomes
from feature_signal.schemas.insights import FeatureTierOut, InsightRunOut
from feature_signal.services.rule_suggest_service import RuleSuggestService

_NATIVE_FIELDS = {"platform", "country", "country_tier", "subscription_state"}


class OfflineDataset(Protocol):
    def users(self) -> pd.DataFrame: ...
    def transactions(self) -> pd.DataFrame: ...


@dataclass(frozen=True)
class PublishedFlow:
    """App-scoped, externally verified flow metadata supplied by the composition root."""

    flow_id: str
    name: str
    published: bool
    highlight_features: frozenset[str] = frozenset()


@dataclass
class InsightState:
    """Demo lifetime: one process. Never exposed directly to callers."""

    runs: dict[str, InsightRunOut] = field(default_factory=dict)
    locks: dict[str, asyncio.Lock] = field(default_factory=dict)


class InsightService:
    def __init__(
        self,
        *,
        dataset: OfflineDataset,
        as_of: str | datetime,
        value_store: ValueStore,
        tier_store: TierStore,
        proposal_sink: ProposalSink,
        rule_repo: RuleRepo,
        published_flows: Mapping[str, PublishedFlow],
        state: InsightState | None = None,
        offline_columns: Sequence[str] = ("ai_edits_first_day", "photos_imported"),
        offline_features: Mapping[str, str] | None = None,
        user_id_map: Mapping[str, str] | None = None,
        live_outcome_rules: frozenset[str] = frozenset(),
        live_dataset: OfflineDataset | None = None,
        explainer: RuleSuggestService | None = None,
        commit: Callable[[], Awaitable[None]] | None = None,
        window_days: int = 90,
    ):
        self.dataset, self.as_of, self.window_days = dataset, as_of, window_days
        self.value_store, self.tier_store, self.proposal_sink = value_store, tier_store, proposal_sink
        self.rule_repo, self.published_flows = rule_repo, dict(published_flows)
        self.state = state if state is not None else InsightState()
        self.offline_columns, self.offline_features = tuple(offline_columns), dict(offline_features or {})
        self.user_id_map = dict(user_id_map or {})
        self.live_outcome_rules = frozenset(live_outcome_rules)
        self.live_dataset = live_dataset
        self.explainer, self.commit = explainer, commit

    def latest(self, app_id: str) -> InsightRunOut | None:
        run = self.state.runs.get(app_id)
        return run.model_copy(deep=True) if run else None

    def _load(self, dataset: OfflineDataset | None = None):
        selected = self.dataset if dataset is None else dataset
        return build_outcomes(selected.users(), selected.transactions(), as_of=self.as_of, window_days=self.window_days)

    @staticmethod
    def _matrix(frame, columns):
        return FeatureMatrix(frame.user_id.tolist(), list(columns), frame[list(columns)].values.tolist())

    def _live_frame(self, frame: pd.DataFrame, matrix: FeatureMatrix):
        reserved = {
            "user_id",
            "net_revenue_90d",
            "install_at",
            "ab_test",
            "flow",
            "placement",
            "paid_transactions_90d",
            "refunded_transactions_90d",
            "platform",
            "country",
            "country_tier",
            "subscription_state",
        }
        if reserved.intersection(matrix.columns):
            raise ValueError("Rule values must not replace outcome or experiment metadata")
        if len(set(matrix.users)) != len(matrix.users) or len(set(matrix.columns)) != len(matrix.columns):
            raise ValueError("Live matrix users and columns must be unique")
        values = pd.DataFrame(matrix.values, columns=matrix.columns, index=matrix.users)
        ids = pd.Series([self.user_id_map.get(user) for user in matrix.users], index=matrix.users)
        ids = ids.loc[ids.isin(frame.user_id)]
        if ids.duplicated().any():
            raise ValueError("Multiple live users map to the same outcome user")
        metadata = frame.set_index("user_id").loc[ids.tolist()].copy()
        metadata.index = ids.index
        for column in matrix.columns:
            metadata[column] = pd.to_numeric(values.loc[ids.index, column], errors="raise")
        metadata.index.name = "user_id"
        return metadata.reset_index()

    @staticmethod
    def _analyse(frame, matrix, feature_map):
        outcomes = frame.set_index("user_id").net_revenue_90d.to_dict()
        rankings = rank(matrix, outcomes)
        tiers = derive_tiers(matrix, outcomes, rankings, feature_map)
        segments = build_segments(frame, tiers)
        uplift = by_segment(frame, segments) if segments else []
        return rankings, tiers, segments, uplift, hypotheses(matrix, outcomes)

    async def run(self, app_id: str, source: str) -> InsightRunOut:
        if source not in {"offline", "live"}:
            raise ValueError("source must be offline or live")
        lock = self.state.locks.setdefault(app_id, asyncio.Lock())
        async with lock:
            frame = await asyncio.to_thread(self._load)
            rules = await self.rule_repo.list(app_id)
            columns = [column for column in self.offline_columns if column in frame]
            matrix = self._matrix(frame, columns)
            feature_map = self.offline_features
            unmeasured = set()
            effective_source = "offline"
            active_dataset = self.dataset
            if source == "live":
                live = await self.value_store.matrix(app_id)
                # IDs alone cannot establish that current values precede historical outcomes.
                # The host must explicitly verify both identity and measurement-window lineage.
                eligible = [key for key in live.columns if key in self.live_outcome_rules]
                unmeasured.update(set(live.columns) - set(eligible))
                selected = [live.columns.index(key) for key in eligible]
                verified = FeatureMatrix(
                    live.users, eligible, [[row[index] for index in selected] for row in live.values]
                )
                live_outcomes = await asyncio.to_thread(self._load, self.live_dataset) if self.live_dataset else frame
                joined = self._live_frame(live_outcomes, verified) if eligible else frame.iloc[:0]
                if not joined.empty:
                    frame = joined
                    matrix = self._matrix(frame, eligible)
                    feature_map = {rule.key: rule.feature for rule in rules if rule.feature}
                    effective_source = "live"
                    active_dataset = self.live_dataset or self.dataset
                else:
                    unmeasured.update(live.columns)
                    # The frozen schema has one key namespace. A colliding historical
                    # column must not make an unverified live rule appear measured.
                    matrix = self._matrix(frame, [key for key in columns if key not in unmeasured])
            rankings, tiers, segments, uplift, missing = await asyncio.to_thread(
                self._analyse, frame, matrix, feature_map
            )
            measured = set(matrix.columns) - set(missing)
            unmeasured.update(missing)
            unmeasured.update(rule.key for rule in rules if rule.key not in measured)
            result = InsightRunOut(
                run_id=f"run_{uuid4().hex[:16]}",
                source=effective_source,
                created_at=datetime.now(timezone.utc),
                rankings=[asdict(item) for item in rankings],
                segments=[asdict(item) for item in segments],
                uplift=[asdict(item) for item in uplift],
                tiers=[FeatureTierOut(**asdict(item), attribute=item.attribute) for item in tiers],
                hypotheses=sorted(unmeasured),
            )
            drafts = []
            for effect in uplift:
                flow = self.published_flows.get(effect.better_arm)
                if effect.ci_low <= 0 or flow is None or not flow.published or not flow.flow_id:
                    continue
                segment = next(item for item in segments if item.segment_key == effect.segment_key)
                fields = {condition.field for condition in segment.conditions}
                tier = next((item for item in tiers if item.passed and item.rule_key in fields), None)
                ranking = next((item for item in rankings if tier and item.feature == tier.rule_key), None)
                refunds = refund_diagnostics(frame, segment, effect.test)
                refund_text = "; ".join(
                    f"{arm}: {values['refunded_transactions']}/{values['paid_transactions']} paid transactions refunded"
                    for arm, values in refunds.items()
                )
                reason = (
                    f"Synthetic data: {effect.better_arm} has ${effect.diff_net_90d:.2f} higher net revenue per user "
                    f"over {self.window_days} days in randomized test '{effect.test}' "
                    f"(90% interval ${effect.ci_low:.2f} to ${effect.ci_high:.2f}). Refunds: {refund_text}. "
                    "Hypothesis: behavioral differences may reflect different user needs."
                )
                if self.explainer is not None and ranking is not None:
                    explanation = await self.explainer.explain(app_id, ranking)
                    reason += f" {explanation.summary} Hypothesis: {explanation.hypothesis}"
                highlight = tier.feature if tier and tier.feature in flow.highlight_features else None
                drafts.append(
                    ProposalDraft(
                        segment_key=segment.segment_key,
                        trigger_placement=RANDOMIZED_TESTS[effect.test][0],
                        condition=Condition("p_segment", "IN", [segment.segment_key]),
                        flow_id=flow.flow_id,
                        flow_name=flow.name,
                        expected_diff=effect.diff_net_90d,
                        ci_low=effect.ci_low,
                        ci_high=effect.ci_high,
                        reason=reason,
                        highlight_feature=highlight,
                        adapty_filters=[
                            Condition(item.field, "IN", [item.value]) if item.op in {"=", "=="} else item
                            for item in segment.conditions
                            if item.field in _NATIVE_FIELDS
                        ],
                        evidence={
                            "source": effective_source,
                            "requested_source": source,
                            "synthetic": True,
                            "dataset": dict(getattr(active_dataset, "provenance", {})),
                            "as_of": pd.Timestamp(self.as_of).isoformat(),
                            "outcome_window_days": self.window_days,
                            "segment_conditions": [
                                asdict(item) for item in segment.conditions if item.field not in _NATIVE_FIELDS
                            ],
                            "analysis_conditions": [asdict(item) for item in segment.conditions],
                            "randomized_test": effect.test,
                            "better_arm": effect.better_arm,
                            "worse_arm": effect.worse_arm,
                            "n_a": effect.n_a,
                            "n_b": effect.n_b,
                            "refunds": refunds,
                        },
                    )
                )
            # SQL-backed adapters share the request transaction; commit only after both succeed.
            # Other port implementations must supply their own transactional guarantees.
            await self.tier_store.put_many(app_id, tiers)
            if drafts:
                await self.proposal_sink.create_many(app_id, drafts)
            if self.commit:
                await self.commit()
            self.state.runs[app_id] = result.model_copy(deep=True)
            return result

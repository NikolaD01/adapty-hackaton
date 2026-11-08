"""Rule suggestions and insight routes (owner B)."""

from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from feature_signal.core.config import Settings, get_settings
from feature_signal.core.errors import ApiError
from feature_signal.db.session import get_session
from feature_signal.integrations.llm.provider import OpenAILLMProvider
from feature_signal.integrations.offline import CsvOfflineDataset
from feature_signal.repositories.event_types import EventTypeRepository
from feature_signal.repositories.features import FeatureRepository
from feature_signal.repositories.rules import RuleRepository
from feature_signal.repositories.tiers import TierRepository
from feature_signal.repositories.values import ValueRepository
from feature_signal.schemas.insights import InsightRunIn, InsightRunOut
from feature_signal.schemas.rules import RuleIn, RuleSuggestion, RuleSuggestionsOut
from feature_signal.services.insight_service import InsightService, InsightState, OfflineDataset, PublishedFlow
from feature_signal.services.rule_suggest_service import RuleSuggestService

router = APIRouter(tags=["brain (B)"])


@dataclass
class BrainRuntime:
    """App-specific inputs supplied by the host; no global flow or user-ID guesses."""

    as_of: str
    proposal_sink_factory: Callable
    published_flows: dict[str, PublishedFlow]
    dataset: OfflineDataset | None = None
    live_dataset: OfflineDataset | None = None
    offline_columns: tuple[str, ...] = ("ai_edits_first_day", "photos_imported")
    offline_features: dict[str, str] = field(default_factory=dict)
    user_id_map: dict[str, str] = field(default_factory=dict)
    live_outcome_rules: frozenset[str] = frozenset()
    explain: bool = True
    outcome_window_days: int = 90  # the purchase window of the outcome metric; 90 unless the team decides otherwise
    state: InsightState = field(default_factory=InsightState)


def configure_brain(app, app_id: str, runtime: BrainRuntime) -> None:
    if not hasattr(app.state, "brain_runtimes"):
        app.state.brain_runtimes = {}
    app.state.brain_runtimes[app_id] = runtime


async def insight_service(
    app_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    runtime = getattr(request.app.state, "brain_runtimes", {}).get(app_id)
    if runtime is None:
        raise ApiError(
            503,
            "brain_not_configured",
            "Configure Brain with an explicit dataset cutoff, app-scoped ProposalSink and verified published flows",
        )
    async with AsyncExitStack() as stack:
        explainer = None
        if runtime.explain and settings.llm_provider == "openai" and settings.openai_api_key.get_secret_value():
            client = await stack.enter_async_context(
                AsyncOpenAI(
                    api_key=settings.openai_api_key.get_secret_value(),
                    timeout=30,
                    max_retries=0,
                )
            )
            explainer = RuleSuggestService(
                feature_repo=FeatureRepository(session),
                event_repo=EventTypeRepository(session),
                rule_repo=RuleRepository(session),
                provider_factory=lambda context: OpenAILLMProvider(settings=settings, client=client, context=context),
            )
        yield InsightService(
            dataset=runtime.dataset or CsvOfflineDataset(settings.offline_data_dir),
            as_of=runtime.as_of,
            value_store=ValueRepository(session),
            tier_store=TierRepository(session),
            proposal_sink=runtime.proposal_sink_factory(session),
            rule_repo=RuleRepository(session),
            published_flows=runtime.published_flows,
            offline_columns=runtime.offline_columns,
            offline_features=runtime.offline_features,
            user_id_map=runtime.user_id_map,
            live_outcome_rules=runtime.live_outcome_rules,
            live_dataset=runtime.live_dataset,
            state=runtime.state,
            explainer=explainer,
            commit=session.commit,
            window_days=runtime.outcome_window_days,
        )


async def llm_provider_factory(settings: Annotated[Settings, Depends(get_settings)]):
    if settings.llm_provider != "openai" or not settings.openai_api_key.get_secret_value():
        raise ApiError(503, "llm_not_configured", "Configure OPENAI_API_KEY and LLM_PROVIDER=openai")
    async with AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=30, max_retries=0) as client:
        yield lambda context: OpenAILLMProvider(settings=settings, client=client, context=context)


def rule_suggest_service(
    app_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    factory: Annotated[Callable, Depends(llm_provider_factory)],
) -> RuleSuggestService:
    properties = getattr(request.app.state, "brain_property_allowlists", {}).get(app_id, {})
    return RuleSuggestService(
        feature_repo=FeatureRepository(session),
        event_repo=EventTypeRepository(session),
        rule_repo=RuleRepository(session),
        provider_factory=factory,
        property_allowlist=properties,
    )


@router.post("/apps/{app_id}/rules:suggest", response_model=RuleSuggestionsOut)
async def suggest_rules(
    app_id: str, service: Annotated[RuleSuggestService, Depends(rule_suggest_service)]
) -> RuleSuggestionsOut:
    suggestions = await service.suggest(app_id)
    return RuleSuggestionsOut(
        model=service.model_name,
        suggestions=[
            RuleSuggestion(rule=RuleIn.model_validate(asdict(rule)), rationale=text) for rule, text in suggestions
        ],
    )


@router.post("/apps/{app_id}/insights:run", response_model=InsightRunOut)
async def run_insights(
    app_id: str, body: InsightRunIn, service: Annotated[InsightService, Depends(insight_service)]
) -> InsightRunOut:
    try:
        return await service.run(app_id, body.source)
    except ValueError as error:
        raise ApiError(422, "invalid_insight_data", str(error)) from error


@router.get("/apps/{app_id}/insights/latest", response_model=InsightRunOut)
async def latest_insights(app_id: str, service: Annotated[InsightService, Depends(insight_service)]) -> InsightRunOut:
    result = service.latest(app_id)
    if result is None:
        raise ApiError(404, "insight_not_found", "No successful insight run exists for this app")
    return result

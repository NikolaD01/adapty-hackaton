"""Served-flow lookup route for the demo (owner C)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from feature_signal.core.config import get_settings
from feature_signal.domain.ports import FlowLookup
from feature_signal.integrations.adapty.lookup import AdaptyFlowLookup
from feature_signal.schemas.proposals import LookupIn, LookupOut, LookupResult
from feature_signal.services.lookup_service import LookupService

router = APIRouter(tags=["lookup (C)"])


def get_flow_lookup(request: Request) -> FlowLookup:
    """`app.state.flow_lookup` if set (tests), otherwise the real Adapty lookup, built once."""
    lookup = getattr(request.app.state, "flow_lookup", None)
    if lookup is None:
        lookup = AdaptyFlowLookup.from_settings(get_settings())
        request.app.state.flow_lookup = lookup
    return lookup


@router.post("/apps/{app_id}/lookup", response_model=LookupOut)
async def lookup(
    app_id: str, body: LookupIn, flow_lookup: Annotated[FlowLookup, Depends(get_flow_lookup)]
) -> LookupOut:
    served = await LookupService(flow_lookup).lookup(body.placement, body.customer_user_ids)
    return LookupOut(
        results=[
            LookupResult(
                customer_user_id=s.customer_user_id,
                segment_hash=s.segment_hash,
                flow_id=s.flow_id,
                flow_name=s.flow_name,
            )
            for s in served
        ]
    )

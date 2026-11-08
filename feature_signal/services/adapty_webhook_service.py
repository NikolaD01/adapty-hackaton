"""Adapty webhook → our event history (owner A).

Adapty's purchase events (subscription_started, renewals, refunds, trials …) become events with key
`adapty_<event_type>` for the same `customer_user_id`, so outcomes are measured on real Adapty purchases.
Docs: https://adapty.io/docs/webhook-event-types-and-fields · https://adapty.io/docs/set-up-webhook-integration
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from feature_signal.domain.models import Event, Rule, RuleDefinition

NAMESPACE = uuid.UUID("0e8f8b52-1c6f-4d8e-9f0a-6d2b1a7c3e44")
PREFIX = "adapty_"

# Positive: money in. Negative: money back. Net revenue = sum of `net_revenue_signed_usd`.
REVENUE_SIGN = {
    "subscription_started": 1,
    "subscription_initial_purchase": 1,
    "subscription_renewed": 1,
    "trial_converted": 1,
    "non_subscription_purchase": 1,
    "subscription_refunded": -1,
    "non_subscription_purchase_refunded": -1,
}
DESCRIPTIONS = {
    "subscription_started": "Adapty: a paid subscription started without a trial",
    "subscription_renewed": "Adapty: a subscription renewal was charged",
    "subscription_renewal_cancelled": "Adapty: auto-renewal was turned off",
    "subscription_expired": "Adapty: a subscription ended",
    "subscription_refunded": "Adapty: a subscription was refunded",
    "non_subscription_purchase": "Adapty: a one-time purchase",
    "non_subscription_purchase_refunded": "Adapty: a one-time purchase was refunded",
    "trial_started": "Adapty: a trial started",
    "trial_converted": "Adapty: a trial converted to the first paid period",
    "trial_expired": "Adapty: a trial ended without converting",
    "billing_issue_detected": "Adapty: a charge attempt failed",
    "access_level_updated": "Adapty: the user's access level changed",
}
# Flat, scalar fields kept as props (event_properties has only scalars per the docs).
KEEP = (
    "price_usd",
    "proceeds_usd",
    "net_revenue_usd",
    "profile_total_revenue_usd",
    "currency",
    "store",
    "vendor_product_id",
    "environment",
    "transaction_id",
    "profile_has_access_level",
    "cancellation_reason",
    "developer_id",
    "paywall_name",
    "flow_id",
    "flow_name",
    "variation_id",
    "ab_test_name",
    "ab_test_variant_name",
    "cohort_name",
)
NET_REVENUE_RULE = "adapty_net_revenue_90d"


def event_key(event_type: str) -> str:
    """Event types can be renamed in the Adapty dashboard: keep any name, made safe for our key pattern."""
    slug = re.sub(r"[^a-z0-9_]+", "_", event_type.lower()).strip("_") or "unknown"
    return (PREFIX + slug)[:40]


def description(event_type: str) -> str:
    return DESCRIPTIONS.get(event_type, f"Adapty webhook event {event_type}")


def _scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value[:100]
    return None


def _when(value: Any) -> datetime:
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(value, fmt).astimezone(timezone.utc)
            except ValueError:
                pass
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def to_event(payload: dict[str, Any]) -> Event | None:
    """One webhook body → one Event, or None for the empty verification request / unusable bodies."""
    event_type = payload.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        return None
    user = payload.get("customer_user_id") or (
        f"adapty_profile:{payload['profile_id']}" if payload.get("profile_id") else None
    )
    if not user:
        return None
    ep = payload.get("event_properties") or {}
    props = {k: _scalar(ep[k]) for k in KEEP if k in ep and (ep[k] is None or _scalar(ep[k]) is not None)}
    sign = REVENUE_SIGN.get(event_type)
    net = _scalar(ep.get("net_revenue_usd"))
    if sign is not None and isinstance(net, float):
        props["net_revenue_signed_usd"] = sign * abs(net)
    dedupe = ep.get("profile_event_id") or f"{ep.get('transaction_id')}:{event_type}:{payload.get('event_datetime')}"
    return Event(
        event_id=str(uuid.uuid5(NAMESPACE, f"{payload.get('profile_id')}:{dedupe}")),
        customer_user_id=str(user)[:128],
        key=event_key(event_type),
        occurred_at=_when(payload.get("event_datetime") or ep.get("event_datetime")),
        props=props,
    )


def net_revenue_rule() -> Rule:
    """The plan's metric, live: net revenue (purchases minus refunds) in 90 days from Adapty webhooks."""
    keys = sorted({event_key(t) for t in REVENUE_SIGN})
    return Rule(
        key=NET_REVENUE_RULE,
        name="Net revenue in 90 days (Adapty)",
        description="Sum of net_revenue_signed_usd from Adapty purchase and refund webhooks, 90 days",
        definition=RuleDefinition(event_keys=keys, measure="sum", value_prop="net_revenue_signed_usd", window_days=90),
        source="default",
    )

"""Rules: how a value is derived from events (owner A). Pure functions, no I/O.

`default_rules` — the values every feature gets automatically (docs/contracts/api.md, Feature).
`apply` (chapter 5) — evaluates one rule over one user's events.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from feature_signal.domain.models import Event, Rule, RuleDefinition, Where

WINDOW_7D = 7


def default_rules(feature_key: str, feature_name: str, event_keys: list[str]) -> list[Rule]:
    """Default values for a feature: uses in total, uses in 7 days, active days in 7 days, and one
    "used it" flag per event. Empty when the feature has no events yet (a rule needs at least one)."""
    events = sorted(set(event_keys))
    if not events:
        return []

    def rule(key: str, name: str, description: str, definition: RuleDefinition) -> Rule:
        return Rule(
            key=key, name=name, description=description, definition=definition, source="default", feature=feature_key
        )

    rules = [
        rule(
            f"{feature_key}_uses_total",
            f"{feature_name}: uses in total",
            f"Number of {feature_name} events in the whole history",
            RuleDefinition(event_keys=events, measure="count"),
        ),
        rule(
            f"{feature_key}_uses_7d",
            f"{feature_name}: uses in 7 days",
            f"Number of {feature_name} events in the last 7 days",
            RuleDefinition(event_keys=events, measure="count", window_days=WINDOW_7D),
        ),
        rule(
            f"{feature_key}_days_active_7d",
            f"{feature_name}: active days in 7 days",
            f"Days with at least one {feature_name} event in the last 7 days",
            RuleDefinition(event_keys=events, measure="days_active", window_days=WINDOW_7D),
        ),
    ]
    rules += [
        rule(
            f"{feature_key}_used_{event}",
            f"{feature_name}: used {event}",
            f"1 if the user ever sent {event}, else 0",
            RuleDefinition(event_keys=[event], measure="exists"),
        )
        for event in events
    ]
    return rules


# ---------- evaluation (chapter 5) ---------------------------------------------------------------


def _number(value: object) -> float | None:
    """A numeric prop value; bools and strings don't count as numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _matches(where: Where | None, event: Event) -> bool:
    if where is None:
        return True
    if where.prop not in event.props:
        return False
    actual = event.props[where.prop]
    if where.op == "eq":
        a, b = _number(actual), _number(where.value)
        if a is not None and b is not None:
            return a == b  # 0 == 0.0
        return type(actual) is type(where.value) and actual == where.value  # True != 1, "1" != 1
    a, b = _number(actual), _number(where.value)
    if a is None or b is None:
        return False
    return {"lt": a < b, "lte": a <= b, "gt": a > b, "gte": a >= b}[where.op]


def _select(keys: list[str], rule: RuleDefinition, events: list[Event], now: datetime) -> list[Event]:
    since = now - timedelta(days=rule.window_days) if rule.window_days else None
    wanted = set(keys)
    return [
        e for e in events if e.key in wanted and (since is None or e.occurred_at >= since) and _matches(rule.where, e)
    ]


def apply(rule: RuleDefinition, events: list[Event], now: datetime) -> float:
    """Value of one rule for one user's events. Windows use occurred_at (inclusive lower bound
    `now - window_days`), never received_at. Missing props are skipped; nothing matching → 0."""
    picked = _select(rule.event_keys, rule, events, now)
    m = rule.measure
    if m == "count":
        return float(len(picked))
    if m == "exists":
        return 1.0 if picked else 0.0
    if m == "distinct":
        return float(len({e.props[rule.distinct_prop] for e in picked if rule.distinct_prop in e.props}))
    if m == "days_active":
        return float(len({e.occurred_at.astimezone(timezone.utc).date() for e in picked}))
    if m == "ratio":
        denominator = len(_select(rule.denominator_event_keys or [], rule, events, now))
        return len(picked) / denominator if denominator else 0.0
    values = [(e.occurred_at, v) for e in picked if (v := _number(e.props.get(rule.value_prop))) is not None]
    if not values:
        return 0.0
    if m == "sum":
        return sum(v for _, v in values)
    if m == "max":
        return max(v for _, v in values)
    if m == "min":
        return min(v for _, v in values)
    if m == "last":
        return max(values, key=lambda tv: tv[0])[1]
    raise ValueError(f"unknown measure {m}")

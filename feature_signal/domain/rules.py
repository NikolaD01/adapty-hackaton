"""Rules: how a value is derived from events (owner A). Pure functions, no I/O.

`default_rules` — the values every feature gets automatically (docs/contracts/api.md, Feature).
`apply` (chapter 5) — evaluates one rule over one user's events.
"""

from __future__ import annotations

from feature_signal.domain.models import Rule, RuleDefinition

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

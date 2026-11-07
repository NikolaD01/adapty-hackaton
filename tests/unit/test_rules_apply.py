"""A6: every rule measure, the where filter and the window boundary (pure, no I/O)."""

from datetime import datetime, timedelta, timezone

import pytest

from feature_signal.domain.models import Event, RuleDefinition, Where
from feature_signal.domain.rules import apply

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def ev(key: str, days_ago: float = 0, **props) -> Event:
    return Event(
        event_id=f"{key}-{days_ago}-{props}",
        customer_user_id="u",
        key=key,
        occurred_at=NOW - timedelta(days=days_ago),
        received_at=NOW,
        props=props,
    )


EVENTS = [
    ev("generate_click", 0.1, photo_id="p1", tokens_used=40, tokens_left=40),
    ev("generate_click", 1.0, photo_id="p2", tokens_used=40, tokens_left=0),
    ev("regenerate_click", 1.1, photo_id="p2", tokens_used=40, tokens_left=0),
    ev("generate_click", 3.0, photo_id="p1", tokens_used=20),
    ev("generate_click", 10.0, photo_id="p9", tokens_used=99),  # outside 7 days
    ev("export", 0.5),
]


def d(**kw) -> RuleDefinition:
    kw.setdefault("event_keys", ["generate_click", "regenerate_click"])
    return RuleDefinition(**kw)


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        (d(measure="count"), 5),
        (d(measure="count", window_days=7), 4),
        (d(measure="distinct", distinct_prop="photo_id", window_days=7), 2),
        (d(measure="exists", event_keys=["export"]), 1),
        (d(measure="exists", event_keys=["nothing"]), 0),
        (d(measure="days_active", window_days=7), 3),  # 0.1 and 1.0/1.1 days ago fall on two dates + 3 days ago
        (
            d(
                measure="ratio",
                event_keys=["regenerate_click"],
                denominator_event_keys=["generate_click"],
                window_days=7,
            ),
            1 / 3,
        ),
        (d(measure="sum", value_prop="tokens_used", window_days=7), 140),
        (d(measure="max", value_prop="tokens_used"), 99),
        (d(measure="min", value_prop="tokens_used", window_days=7), 20),
        (d(measure="last", value_prop="tokens_left"), 40),  # the latest event has tokens_left=40
        (d(measure="exists", where=Where(prop="tokens_left", op="lte", value=0), window_days=7), 1),
        (d(measure="count", where=Where(prop="tokens_left", op="lte", value=0)), 2),
        (d(measure="count", where=Where(prop="photo_id", op="eq", value="p1")), 2),
    ],
)
def test_measures(definition, expected):
    assert apply(definition, EVENTS, NOW) == pytest.approx(expected)


def test_days_active_counts_dates_not_events():
    events = [ev("generate_click", 0.01), ev("generate_click", 0.02), ev("generate_click", 2)]
    assert apply(d(measure="days_active"), events, NOW) == 2


def test_window_lower_bound_is_inclusive():
    at_edge = [ev("generate_click", 7.0)]
    just_out = [ev("generate_click", 7.0001)]
    assert apply(d(measure="count", window_days=7), at_edge, NOW) == 1
    assert apply(d(measure="count", window_days=7), just_out, NOW) == 0


def test_window_uses_occurred_at_not_received_at():
    late = Event(
        event_id="x",
        customer_user_id="u",
        key="generate_click",
        occurred_at=NOW - timedelta(days=9),
        received_at=NOW,
        props={},
    )
    assert apply(d(measure="count", window_days=7), [late], NOW) == 0


def test_ratio_with_zero_denominator_is_zero():
    assert apply(d(measure="ratio", event_keys=["regenerate_click"], denominator_event_keys=["nope"]), EVENTS, NOW) == 0


def test_value_measures_skip_missing_strings_and_bools():
    events = [
        ev("generate_click", 0, tokens_used="40"),
        ev("generate_click", 0, tokens_used=True),
        ev("generate_click", 0),
    ]
    assert apply(d(measure="sum", value_prop="tokens_used"), events, NOW) == 0


def test_where_on_a_missing_prop_or_wrong_type_does_not_match():
    events = [ev("generate_click", 0), ev("generate_click", 0, tokens_left="none")]
    assert apply(d(measure="count", where=Where(prop="tokens_left", op="lte", value=0)), events, NOW) == 0


def test_no_events_gives_zero_for_every_measure():
    for m, extra in [
        ("count", {}),
        ("distinct", {"distinct_prop": "p"}),
        ("exists", {}),
        ("days_active", {}),
        ("ratio", {"denominator_event_keys": ["x"]}),
        ("sum", {"value_prop": "v"}),
        ("last", {"value_prop": "v"}),
    ]:
        assert apply(d(measure=m, **extra), [], NOW) == 0


def test_eq_compares_numbers_by_value_and_other_types_strictly():
    events = [
        ev("generate_click", 0, tokens_left=0.0),
        ev("generate_click", 0, with_upload=True),
        ev("generate_click", 0, with_upload=1),
    ]
    assert apply(d(measure="count", where=Where(prop="tokens_left", op="eq", value=0)), events, NOW) == 1
    assert apply(d(measure="count", where=Where(prop="with_upload", op="eq", value=True)), events, NOW) == 1

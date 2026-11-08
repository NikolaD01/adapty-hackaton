"""The outcome window is a setting (default 90 days); shorter windows keep more users and say so everywhere."""

import pandas as pd
import pytest

from feature_signal.integrations.offline import build_outcomes
from feature_signal.schemas.proposals import ExpectedEffect

AS_OF = "2026-05-01T00:00:00Z"


def frames():
    users = pd.DataFrame(
        {
            "user_id": ["old", "mid", "new"],
            "install_at": [
                "2026-01-01T00:00:00Z",
                "2026-03-20T00:00:00Z",
                "2026-04-25T00:00:00Z",
            ],  # 120 d, 42 d, 6 d old
        }
    )
    tx = pd.DataFrame(
        {
            "user_id": ["old", "old", "mid", "mid"],
            # old: day 4 and day 73 after install; mid: day 5 and day 39 after install
            "purchased_at": [
                "2026-01-05T00:00:00Z",
                "2026-03-15T00:00:00Z",
                "2026-03-25T00:00:00Z",
                "2026-04-28T00:00:00Z",
            ],
            "price_usd": [10.0, 20.0, 5.0, 7.0],
            "refunded_at": [None, None, None, None],
        }
    )
    return users, tx


def revenue(frame):
    return frame.set_index("user_id").net_revenue_90d.to_dict()


def test_default_window_is_90_days_and_unchanged():
    frame = build_outcomes(*frames(), as_of=AS_OF)
    assert frame.attrs["outcome_window_days"] == 90
    assert revenue(frame) == {"old": 30.0}  # both purchases fall inside 90 days; "mid" is not mature yet


def test_a_30_day_window_keeps_younger_users_and_counts_only_the_first_30_days():
    frame = build_outcomes(*frames(), as_of=AS_OF, window_days=30)
    assert frame.attrs["outcome_window_days"] == 30
    assert revenue(frame) == {
        "old": 10.0,
        "mid": 5.0,
    }  # day 73 and day 39 purchases are outside; "new" is only 6 days old


def test_a_window_longer_than_the_data_keeps_nobody():
    assert build_outcomes(*frames(), as_of=AS_OF, window_days=365).empty


@pytest.mark.parametrize("bad", [0, -1, 366, 1.5, True, "30"])
def test_the_window_must_be_a_whole_number_of_days_between_1_and_365(bad):
    with pytest.raises(ValueError):
        build_outcomes(*frames(), as_of=AS_OF, window_days=bad)


def test_a_refund_seen_after_the_window_still_removes_the_purchase():
    users, tx = frames()
    tx.loc[0, "refunded_at"] = "2026-04-01T00:00:00Z"  # long after the 30-day window, before as_of
    assert revenue(build_outcomes(users, tx, as_of=AS_OF, window_days=30)) == {"old": 0.0, "mid": 5.0}


def test_the_metric_label_follows_the_window():
    assert ExpectedEffect(diff=1, ci_low=0, ci_high=2).metric == "net_revenue_90d"
    assert ExpectedEffect(metric="net_revenue_30d", diff=1, ci_low=0, ci_high=2).metric == "net_revenue_30d"
    with pytest.raises(ValueError):
        ExpectedEffect(metric="revenue", diff=1, ci_low=0, ci_high=2)

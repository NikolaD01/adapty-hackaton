"""C3: the proposal state machine is exactly the one in docs/contracts/api.md."""

import pytest

from feature_signal.core.errors import ApiError
from feature_signal.services.proposal_service import ALLOWED_TRANSITIONS, check_transition

ALL = ["draft", "approved", "executing", "awaiting_publish", "live", "failed", "rejected"]


@pytest.mark.parametrize(
    ("src", "dst"),
    [
        ("draft", "approved"),
        ("draft", "rejected"),
        ("approved", "executing"),
        ("executing", "live"),
        ("executing", "failed"),
        ("executing", "awaiting_publish"),
        ("awaiting_publish", "live"),
        ("awaiting_publish", "executing"),
        ("awaiting_publish", "failed"),
        ("failed", "approved"),
    ],
)
def test_contract_transitions_are_allowed(src, dst):
    check_transition(src, dst)


def test_every_other_transition_is_a_409():
    allowed = {(s, d) for s, ds in ALLOWED_TRANSITIONS.items() for d in ds}
    for src in ALL:
        for dst in ALL:
            if (src, dst) in allowed:
                continue
            with pytest.raises(ApiError) as caught:
                check_transition(src, dst)
            assert (caught.value.status, caught.value.code) == (409, "invalid_transition")


def test_live_and_rejected_are_final():
    for final in ("live", "rejected"):
        assert ALLOWED_TRANSITIONS.get(final, set()) == set()


def test_the_proposal_metric_follows_the_outcome_window_of_the_draft():
    from feature_signal.domain.models import Condition, ProposalDraft
    from feature_signal.services.proposal_service import draft_to_input

    def draft(**evidence):
        return ProposalDraft(
            "s", "main", Condition("p_segment", "IN", ["s"]), "f", "F", 1.0, 0.5, 1.5, "r", evidence=evidence
        )

    assert draft_to_input(draft()).expected_effect.metric == "net_revenue_90d"
    assert draft_to_input(draft(outcome_window_days=30)).expected_effect.metric == "net_revenue_30d"

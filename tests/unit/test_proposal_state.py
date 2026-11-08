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
        ("awaiting_publish", "failed"),
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


def test_live_failed_and_rejected_are_final():
    for final in ("live", "failed", "rejected"):
        assert ALLOWED_TRANSITIONS.get(final, set()) == set()

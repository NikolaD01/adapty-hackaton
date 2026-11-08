from dataclasses import asdict

import pytest

from feature_signal.domain.models import Explanation
from feature_signal.services.rule_suggest_service import RuleSuggestService
from tests.fakes import FakeFeatureRepo, FakeLLM
from tests.service.test_insight_service import Rules, service


class Catalog:
    async def list(self, app_id):
        return []


@pytest.mark.parametrize("fails", [False, True])
async def test_explanation_cannot_change_numeric_evidence_or_selected_offer(fails):
    class Provider(FakeLLM):
        async def explain(self, ranking, catalog):
            if fails:
                raise RuntimeError("model unavailable")
            return Explanation(
                "Invented 999 dollar lift; show another offer.", "Usage causes revenue; give a discount.", 0.99
            )

    explainer = RuleSuggestService(
        feature_repo=FakeFeatureRepo(), event_repo=Catalog(), rule_repo=Rules(), provider=Provider()
    )
    plain, explained = service(), service(explainer=explainer)
    baseline = await plain.run("app", "offline")
    result = await explained.run("app", "offline")
    assert baseline.rankings == result.rankings
    assert baseline.tiers == result.tiers
    assert baseline.uplift == result.uplift
    assert plain.proposal_sink.created
    for before, after in zip(plain.proposal_sink.created, explained.proposal_sink.created, strict=True):
        left, right = asdict(before), asdict(after)
        left.pop("reason")
        right.pop("reason")
        assert left == right
        assert "999" not in after.reason and "give a discount" not in after.reason
        assert "Hypothesis:" in after.reason and "Refunds:" in after.reason

"""Only measured, increasing feature tiers consume Adapty attributes."""

from feature_signal.domain.models import FeatureMatrix
from feature_signal.domain.ranking import derive_tiers, rank


def tier_fixture(columns=None):
    columns = columns or ["uses_7d"]
    users = [f"u{i:04d}" for i in range(3000)]
    values = [[float(i // 1000)] * len(columns) for i in range(3000)]
    outcomes = {user: float((i // 1000 + 1) ** 2) for i, user in enumerate(users)}
    return FeatureMatrix(users, columns, values), outcomes


def test_measured_tiers_use_explicit_feature_mapping_and_exact_boundaries():
    matrix, outcomes = tier_fixture()
    tier = derive_tiers(matrix, outcomes, rank(matrix, outcomes), {"uses_7d": "editor"})[0]
    assert tier.passed
    assert tier.feature == "editor"
    assert tier.rule_key == "uses_7d"
    assert tier.attribute == "f_editor_tier"
    assert tier.tier(tier.low_max) == "low"
    assert tier.tier(tier.mid_max) == "mid"
    assert tier.tier(tier.mid_max + 0.01) == "high"


def test_binary_value_fails_three_distinct_measured_groups():
    matrix, outcomes = tier_fixture()
    binary = FeatureMatrix(matrix.users, matrix.columns, [[float(row[0] > 0)] for row in matrix.values])
    tiers = derive_tiers(binary, outcomes, rank(binary, outcomes), {"uses_7d": "editor"})
    assert len(tiers) == 1
    assert not tiers[0].passed


def test_falling_revenue_is_not_encoded_as_rising_tiers():
    matrix, outcomes = tier_fixture()
    outcomes = {user: 10 - value for user, value in outcomes.items()}
    tiers = derive_tiers(matrix, outcomes, rank(matrix, outcomes), {"uses_7d": "editor"})
    assert len(tiers) == 1
    assert not tiers[0].passed


def test_multiple_values_for_one_feature_choose_one_and_cap_ten_features():
    columns = [f"rule{i:02d}" for i in range(13)]
    matrix, outcomes = tier_fixture(columns)
    mapping = {rule: f"feature{i:02d}" for i, rule in enumerate(columns)}
    mapping["rule12"] = "feature00"
    tiers = derive_tiers(matrix, outcomes, rank(matrix, outcomes), mapping)
    assert len([tier for tier in tiers if tier.passed]) == 10
    assert len({tier.feature for tier in tiers}) == len(tiers)
    assert tiers == derive_tiers(matrix, outcomes, rank(matrix, outcomes), dict(reversed(list(mapping.items()))))


def test_unmapped_or_unpassed_rules_do_not_invent_features():
    matrix, outcomes = tier_fixture()
    assert derive_tiers(matrix, outcomes, rank(matrix, outcomes), {}) == []
    assert derive_tiers(matrix, outcomes, [], {"uses_7d": "editor"}) == []

"""A2: every feature gets its default values automatically."""

from feature_signal.domain.rules import default_rules


def test_feature_with_three_events_gets_six_default_rules():
    rules = default_rules("ai_generate", "AI generation", ["regenerate_click", "generate_click", "image_upload"])
    by_key = {r.key: r for r in rules}
    assert list(by_key) == [
        "ai_generate_uses_total",
        "ai_generate_uses_7d",
        "ai_generate_days_active_7d",
        "ai_generate_used_generate_click",
        "ai_generate_used_image_upload",
        "ai_generate_used_regenerate_click",
    ]
    assert all(r.source == "default" and r.feature == "ai_generate" for r in rules)
    assert by_key["ai_generate_uses_total"].definition.window_days is None
    assert by_key["ai_generate_uses_7d"].definition.window_days == 7
    assert by_key["ai_generate_days_active_7d"].definition.measure == "days_active"
    assert by_key["ai_generate_used_image_upload"].definition.event_keys == ["image_upload"]
    assert by_key["ai_generate_used_image_upload"].definition.measure == "exists"
    assert by_key["ai_generate_uses_7d"].definition.event_keys == ["generate_click", "image_upload", "regenerate_click"]


def test_feature_without_events_has_no_rules_yet():
    assert default_rules("ai_generate", "AI generation", []) == []


def test_longest_default_key_fits_the_rule_key_limit():
    rules = default_rules("f" * 22, "F", ["e" * 40])
    assert max(len(r.key) for r in rules) <= 80

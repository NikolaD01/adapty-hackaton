"""Wiring B into the running app: flows come from Adapty itself, the demo settings are explicit, no network in tests."""

from pathlib import Path

from fastapi import FastAPI
from pydantic import SecretStr

from feature_signal.core.config import Settings
from feature_signal.integrations.adapty.brain_wiring import (
    DEMO_APP_ID,
    LIVE_OUTCOME_RULES,
    OUTCOME_WINDOW_DAYS,
    configure_demo_brain,
    published_flows_from_listing,
)

LISTING = [
    {"id": "f-life", "name": "Main - Lifetime anchor", "status": "published"},
    {"id": "f-main", "name": "Main - 3 plans", "status": "published"},
    {"id": "f-trial", "name": "Onboarding - Annual trial", "status": "published"},
    {"id": "f-week", "name": "Onboarding - Weekly first", "status": "draft"},
    {"id": "f-set", "name": "Settings - Upgrade", "status": "published"},
    {"id": "f-other", "name": "Win-back - Monthly", "status": "published"},
]


def settings(tmp_path: Path, *, adapty_app="9ccde368-e282-4385-a260-18b428560ba5", openai="") -> Settings:
    (tmp_path / "offline").mkdir(exist_ok=True)
    return Settings(
        adapty_app_id=adapty_app,
        offline_data_dir=str(tmp_path / "offline"),
        openai_api_key=SecretStr(openai),
    )


def test_flows_are_matched_by_name_and_keep_their_real_published_state():
    flows = published_flows_from_listing(LISTING)
    assert {k: (v.flow_id, v.published) for k, v in flows.items()} == {
        "main_lifetime": ("f-life", True),
        "main": ("f-main", True),
        "onb_trial": ("f-trial", True),
        "onb_weekly": ("f-week", False),  # a draft is passed on as not published, B refuses it
        "settings": ("f-set", True),
    }
    assert all(not v.highlight_features for v in flows.values())  # we never claim a feature is highlighted


def test_a_missing_flow_is_left_out_not_invented():
    flows = published_flows_from_listing([x for x in LISTING if x["name"] != "Settings - Upgrade"])
    assert "settings" not in flows
    assert "main_lifetime" in flows


def test_the_runtime_is_registered_for_the_demo_app_and_for_the_adapty_app(tmp_path):
    app = FastAPI()
    ok = configure_demo_brain(app, settings(tmp_path), listing=LISTING)
    assert ok
    runtimes = app.state.brain_runtimes
    assert set(runtimes) == {DEMO_APP_ID, "9ccde368-e282-4385-a260-18b428560ba5"}
    runtime = runtimes[DEMO_APP_ID]
    assert runtime.outcome_window_days == OUTCOME_WINDOW_DAYS == 60
    assert "main_lifetime" in runtime.published_flows
    assert len(runtime.user_id_map) == 5000
    assert runtime.explain is False  # no OpenAI key in this settings object
    # no seed file next to the offline folder: no live outcomes, so no live rule is asserted comparable
    assert runtime.live_dataset is None
    assert runtime.live_outcome_rules == frozenset()


def test_with_the_seed_file_present_the_live_rules_are_asserted(tmp_path, monkeypatch):
    (tmp_path / "lumen_dataset.json.gz").write_bytes(b"x")  # only its existence matters, the reader is stubbed
    monkeypatch.setattr(
        "feature_signal.integrations.offline.SeedJsonDataset",
        lambda path, **kwargs: ("seed", Path(path).name, kwargs["limit"], kwargs["as_of"]),
    )
    app = FastAPI()
    assert configure_demo_brain(app, settings(tmp_path), listing=LISTING)
    runtime = app.state.brain_runtimes[DEMO_APP_ID]
    assert runtime.live_dataset == ("seed", "lumen_dataset.json.gz", 5000, "2026-11-08T00:00:00Z")
    assert runtime.live_outcome_rules == LIVE_OUTCOME_RULES


def test_explanations_are_on_only_when_an_openai_key_exists(tmp_path):
    app = FastAPI()
    configure_demo_brain(app, settings(tmp_path, openai="sk-test"), listing=LISTING)
    assert app.state.brain_runtimes[DEMO_APP_ID].explain is True


def test_no_listing_means_the_brain_stays_unconfigured(tmp_path):
    app = FastAPI()
    assert configure_demo_brain(app, settings(tmp_path), listing=None) is False
    assert not getattr(app.state, "brain_runtimes", {})
    assert configure_demo_brain(app, settings(tmp_path), listing=[]) is False


def test_the_demo_app_id_is_not_registered_twice_when_it_equals_the_adapty_app(tmp_path):
    app = FastAPI()
    configure_demo_brain(app, settings(tmp_path, adapty_app=DEMO_APP_ID), listing=LISTING)
    assert list(app.state.brain_runtimes) == [DEMO_APP_ID]

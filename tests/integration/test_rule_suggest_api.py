from feature_signal.api.v1.insights import llm_provider_factory
from feature_signal.core.config import Settings, get_settings
from feature_signal.domain.models import Rule, RuleDefinition
from tests.fakes import FakeLLM


def test_suggestion_route_reads_actual_catalog_and_never_saves(api):
    app_id = "suggest-app"
    assert (
        api.post(
            f"/v1/apps/{app_id}/features",
            json={
                "key": "hd_export",
                "name": "HD export",
                "description": "Export high definition photos",
            },
        ).status_code
        == 200
    )
    assert (
        api.post(
            f"/v1/apps/{app_id}/event-types",
            json={
                "key": "pt_track_hd_export_blocked",
                "name": "HD export blocked",
                "description": "Export blocked by current plan",
                "features": ["hd_export"],
            },
        ).status_code
        == 200
    )
    contexts = []
    catalogs = []

    class Provider(FakeLLM):
        model_name = "test-model"

        async def suggest_rules(self, catalog):
            catalogs.append(catalog)
            return await super().suggest_rules(catalog)

    def factory(context):
        contexts.append(context)
        return Provider(
            [
                (
                    Rule(
                        "hd_blocked_7d",
                        "HD export blocked",
                        "HD export blocked in the last seven days",
                        RuleDefinition(["pt_track_hd_export_blocked"], "exists", window_days=7),
                        source="ai",
                        feature="hd_export",
                    ),
                    "Measure blocked export demand.",
                )
            ]
        )

    api.app.dependency_overrides[llm_provider_factory] = lambda: factory
    response = api.post(f"/v1/apps/{app_id}/rules:suggest")
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "test-model"
    rule = body["suggestions"][0]["rule"]
    assert rule["definition"]["measure"] == "exists"
    assert rule["definition"]["window_days"] == 7
    assert rule["source"] == "ai"
    assert contexts[0].features[0].key == "hd_export"
    assert catalogs[0][0].key == "pt_track_hd_export_blocked"
    assert contexts[0].existing_rules
    # A subsequent request sees exactly the same stored defaults, not our suggestion.
    assert api.post(f"/v1/apps/{app_id}/rules:suggest").status_code == 200
    assert contexts[1].existing_rules == contexts[0].existing_rules
    assert api.post("/v1/apps/another-app/rules:suggest").json()["suggestions"] == []


def test_missing_key_has_actionable_error_without_a_network_call(api):
    api.app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, openai_api_key="")
    response = api.post("/v1/apps/app/rules:suggest")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_not_configured"

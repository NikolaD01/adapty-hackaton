def test_health_ok(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_not_implemented_helper_returns_501_with_error_shape():
    # Every contract route is built now, so check the shape the helper produces on a throwaway route.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from feature_signal.core.errors import ApiError, api_error_handler, not_implemented

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)

    @app.get("/unbuilt")
    async def unbuilt() -> None:
        raise not_implemented("unbuilt")

    r = TestClient(app).get("/unbuilt")
    assert r.status_code == 501
    body = r.json()["error"]
    assert body["code"] == "not_implemented"
    assert set(body) == {"code", "message", "details"}


def test_every_contract_route_is_mounted(client):
    paths = set(client.app.openapi()["paths"])
    expected = {
        "/v1/apps/{app_id}/event-types",
        "/v1/apps/{app_id}/features",
        "/v1/apps/{app_id}/users/{customer_user_id}/features",
        "/v1/apps/{app_id}/membership:sync",
        "/v1/apps/{app_id}/events",
        "/v1/apps/{app_id}/users/{customer_user_id}/timeline",
        "/v1/apps/{app_id}/rules",
        "/v1/apps/{app_id}/values:recompute",
        "/v1/apps/{app_id}/values",
        "/v1/apps/{app_id}/rules:suggest",
        "/v1/apps/{app_id}/insights:run",
        "/v1/apps/{app_id}/insights/latest",
        "/v1/apps/{app_id}/proposals",
        "/v1/proposals/{proposal_id}",
        "/v1/proposals/{proposal_id}:approve",
        "/v1/proposals/{proposal_id}:reject",
        "/v1/apps/{app_id}/decisions",
        "/v1/apps/{app_id}/settings",
        "/v1/apps/{app_id}/lookup",
        "/v1/proposals/{proposal_id}/paywall-draft",
    }
    assert expected <= paths


def test_approve_route_does_not_swallow_suffix(api):
    # The route is built: it reaches the handler (unknown id -> 404 from our code), not the path-parameter route.
    r = api.post("/v1/proposals/pr_01:approve")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "proposal_not_found"

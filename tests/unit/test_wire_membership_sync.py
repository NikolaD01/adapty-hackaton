"""The running app drives the fast loop from ingest only when an Adapty secret is configured."""

from fastapi import FastAPI
from pydantic import SecretStr

from feature_signal.core.config import Settings
from feature_signal.main import create_app, wire_membership_sync
from feature_signal.services.membership_service import SqlMembershipSync


def test_a_secret_wires_the_sync_and_the_writer():
    app = create_app()
    wire_membership_sync(app, Settings(adapty_secret_key=SecretStr("secret_live_x.y")))
    assert isinstance(app.state.membership_sync, SqlMembershipSync)
    assert app.state.attribute_writer is not None


def test_no_secret_wires_nothing():
    app = FastAPI()
    wire_membership_sync(app, Settings(adapty_secret_key=SecretStr("")))
    assert getattr(app.state, "membership_sync", None) is None


def test_create_app_alone_never_wires_it():
    assert getattr(create_app().state, "membership_sync", None) is None


def test_wire_brain_does_nothing_without_an_adapty_secret():
    from feature_signal.main import wire_brain

    app = FastAPI()
    wire_brain(app, Settings(adapty_secret_key=SecretStr("")))
    assert not getattr(app.state, "brain_runtimes", {})


def test_importing_main_wires_nothing_and_calls_nothing():
    # Tests import this module; with a local .env the wiring would otherwise reach Adapty during a test run.
    import feature_signal.main as main

    assert getattr(main.app.state, "membership_sync", None) is None
    assert not getattr(main.app.state, "brain_runtimes", {})


def test_the_server_startup_runs_both_wirings(monkeypatch):
    from fastapi.testclient import TestClient

    import feature_signal.main as main

    calls = []
    monkeypatch.setattr(main, "wire_membership_sync", lambda app, settings: calls.append("sync"))
    monkeypatch.setattr(main, "wire_brain", lambda app, settings: calls.append("brain"))
    with TestClient(create_app(lifespan=main.wire_running_app)):
        assert calls == ["sync", "brain"]

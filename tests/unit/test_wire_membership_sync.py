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

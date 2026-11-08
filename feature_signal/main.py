"""App entry: `uvicorn feature_signal.main:app --reload`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from feature_signal.api.v1.router import api_router
from feature_signal.core.config import Settings, get_settings
from feature_signal.core.errors import ApiError, api_error_handler


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Feature Signal for Adapty", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(api_router)
    return app


def wire_membership_sync(app: FastAPI, settings: Settings) -> None:
    """Let ingest drive the fast loop: after every committed batch, write only the changed Adapty attributes.

    Done for the running app only (below), never inside `create_app()`, so tests never write to Adapty.
    Skipped without an Adapty secret key; ingest then simply does not sync (it treats the hook as optional).
    """
    secret = settings.adapty_secret_key.get_secret_value()
    if not secret:
        return
    from feature_signal.db.session import SessionFactory
    from feature_signal.integrations.adapty.profile_client import AdaptyProfileClient
    from feature_signal.services.membership_service import SqlMembershipSync

    writer = AdaptyProfileClient.from_settings(settings)
    app.state.attribute_writer = writer
    app.state.membership_sync = SqlMembershipSync(SessionFactory, writer)


app = create_app()
wire_membership_sync(app, get_settings())

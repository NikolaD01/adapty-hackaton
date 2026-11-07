"""App entry: `uvicorn feature_signal.main:app --reload`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from feature_signal.api.v1.router import api_router
from feature_signal.core.config import get_settings
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


app = create_app()

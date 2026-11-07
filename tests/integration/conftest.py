"""Shared integration fixtures: a migrated SQLite file per test and an API client bound to it.

Any area can use `db_url` (sync URL, already at Alembic head) and `api` (TestClient whose
`get_session` dependency uses that database).
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from feature_signal.db.session import get_session, make_engine
from feature_signal.main import create_app

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def db_url(tmp_path) -> str:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


@pytest.fixture
def api(db_url):
    app = create_app()
    engine = make_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"))
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as client:
        yield client

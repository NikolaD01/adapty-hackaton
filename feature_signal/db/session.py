"""Async engine and session factory (owner A). SQLite runs in WAL mode so demo reads don't block ingest."""

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from feature_signal.core.config import get_settings


def _sqlite_pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001 — DB-API connection
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def make_engine(url: str) -> AsyncEngine:
    eng = create_async_engine(url, future=True)
    if url.startswith("sqlite"):
        event.listen(eng.sync_engine, "connect", _sqlite_pragmas)
    return eng


def enable_sqlite_pragmas(sync_engine: Engine) -> None:
    """Same pragmas for a sync engine (migrations, tests)."""
    event.listen(sync_engine, "connect", _sqlite_pragmas)


engine = make_engine(get_settings().database_url)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

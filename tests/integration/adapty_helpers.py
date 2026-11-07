"""Session factory for role C's integration tests: NullPool, so every connection closes with its session."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from feature_signal.db.session import enable_sqlite_pragmas


def make_factory(db_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(db_url.replace("sqlite://", "sqlite+aiosqlite://"), future=True, poolclass=NullPool)
    enable_sqlite_pragmas(engine.sync_engine)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

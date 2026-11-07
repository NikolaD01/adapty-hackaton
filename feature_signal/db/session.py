"""Async engine and session factory (owner A)."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from feature_signal.core.config import get_settings

engine = create_async_engine(get_settings().database_url, future=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

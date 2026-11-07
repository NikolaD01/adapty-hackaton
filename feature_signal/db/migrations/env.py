"""Alembic environment (owner A). Runs migrations with a sync driver on the same database as the app."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from feature_signal.core.config import get_settings
from feature_signal.db.session import enable_sqlite_pragmas
from feature_signal.db.tables import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def sync_url() -> str:
    """Tests pass sqlalchemy.url; otherwise use DATABASE_URL with the async driver swapped for a sync one."""
    url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
    return url.replace("+aiosqlite", "")


def run_migrations_offline() -> None:
    context.configure(url=sync_url(), target_metadata=target_metadata, render_as_batch=True, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = sync_url()
    engine = create_engine(url)
    if url.startswith("sqlite"):
        enable_sqlite_pragmas(engine)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

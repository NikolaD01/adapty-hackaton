"""SQLAlchemy tables. Owner A: every table, including C's proposals/decisions (docs/team/A-ingest-rules.md)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

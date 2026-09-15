"""
Database engine/session setup.

Defaults to SQLite for free, zero-setup local development
(`DATABASE_URL=sqlite:///./dev.db`), and works unchanged with PostgreSQL
in production (`DATABASE_URL=postgresql://user:pass@host/db`) -- nothing
in the models or CRUD layer is SQLite-specific.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables if they don't already exist (MVP approach --
    a real production system would use Alembic migrations instead; see
    README.md 'Future Improvements')."""
    from app.database import models  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

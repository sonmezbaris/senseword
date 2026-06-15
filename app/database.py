"""Database configuration and session management.

For the MVP we use SQLite, but the setup is written so that switching to
PostgreSQL later only requires changing the ``DATABASE_URL`` environment
variable (e.g. ``postgresql+psycopg://user:pass@localhost/senseword``).
"""

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Default to a local SQLite file. Override with the DATABASE_URL env var to
# point at PostgreSQL (or any other SQLAlchemy-supported database) in prod.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./senseword.db")

# SQLite needs this flag because it otherwise refuses to share a connection
# across threads, which FastAPI does. Other databases ignore connect_args.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class that all ORM models inherit from."""


def get_db():
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Called on application startup for the MVP.

    For larger schema changes use Alembic migrations instead.
    """
    # Import models so they are registered on the metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations() -> None:
    """Add new columns to existing tables when needed (MVP-safe).

    ``create_all`` creates missing *tables* but never alters existing ones, so
    a column added to a model after the DB was first created would be missing.
    For the MVP we patch this with a tiny, idempotent ``ADD COLUMN`` step
    instead of pulling in Alembic. Safe to run on every startup.
    """
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "learning_goal" not in user_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN learning_goal VARCHAR"))

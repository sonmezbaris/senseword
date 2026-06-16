"""Database configuration and session management.

For the MVP we use SQLite, but the setup is written so that switching to
PostgreSQL later only requires changing the ``DATABASE_URL`` environment
variable (e.g. ``postgresql+psycopg://user:pass@localhost/senseword``).
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Project root (the ``senseword/`` folder that contains ``app/``). Using an
# absolute path means the SQLite file is always found regardless of the current
# working directory the server was started from.
BASE_DIR = Path(__file__).resolve().parent.parent

# Default to a local SQLite file. Override with the DATABASE_URL env var to
# point at PostgreSQL (or any other SQLAlchemy-supported database) in prod.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'senseword.db'}")

# SQLite needs this flag because it otherwise refuses to share a connection
# across threads, which FastAPI does. Other databases ignore connect_args.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def safe_database_url(url: str = DATABASE_URL) -> str:
    """Return DATABASE_URL with any credentials masked, safe for logging.

    SQLite URLs (no credentials) are returned as-is. For networked databases
    like ``postgresql://user:pass@host/db`` the user:password section is
    replaced with ``***`` so secrets never reach the logs.
    """
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    # rest looks like "user:pass@host/db" -> keep only the part after "@".
    host_part = rest.partition("@")[2]
    return f"{scheme}://***@{host_part}"


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

    # Subscription columns (existing users default to Free / inactive).
    subscription_columns = [
        ("plan", "VARCHAR", "'free'"),
        ("subscription_status", "VARCHAR", "'inactive'"),
        ("subscription_provider", "VARCHAR", "'manual'"),
        ("subscription_customer_id", "VARCHAR", None),
        ("subscription_id", "VARCHAR", None),
        ("subscription_current_period_end", "DATETIME", None),
        ("updated_at", "DATETIME", None),
    ]
    for col_name, col_type, default in subscription_columns:
        if col_name not in user_columns:
            with engine.begin() as conn:
                if default is not None:
                    conn.execute(
                        text(
                            f"ALTER TABLE users ADD COLUMN {col_name} "
                            f"{col_type} DEFAULT {default}"
                        )
                    )
                else:
                    conn.execute(
                        text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    )

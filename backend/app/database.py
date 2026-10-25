"""SQLAlchemy database engine and session factory.

This module creates the database engine from the DATABASE_URL in settings,
and provides a session factory that the rest of the application uses to
talk to the database.

For automated tests, the DATABASE_URL can be overridden to point at an
in-memory SQLite database (see tests/conftest.py).  In production, the
URL should always point to PostgreSQL.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# PostgreSQL uses psycopg (psycopg3); SQLite is used only for tests.
# The `connect_args` and `check_same_thread` options are required for
# SQLite in tests, and are silently ignored by PostgreSQL.
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def get_db():
    """FastAPI dependency that yields a database session.

    Usage in a router::

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    The session is automatically closed when the request finishes,
    even if an error occurs.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

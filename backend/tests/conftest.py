"""Shared pytest fixtures for database tests and HTTP endpoint tests.

Provides two fixtures:
- db_session:  An isolated SQLite session for unit-level ORM tests.
               Never touches the production PostgreSQL database.
- app_client:  A FastAPI TestClient wired to the same SQLite database.
               Used by auth and other HTTP endpoint tests.

The schema is built from SQLAlchemy model metadata (not Alembic) so
tests stay fast and independent of migration files.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (  # noqa: F401 — imported for model registration
    User,
    Resume,
    JobDescription,
    JobMatch,
    SkillGap,
    InterviewSession,
    JobApplication,
)


def _make_sqlite_engine():
    """Create an in-memory SQLite engine with FK enforcement enabled."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture()
def db_session():
    """Yield a database session backed by an in-memory SQLite database.

    The schema is created from the SQLAlchemy model metadata (not Alembic)
    so tests stay fast and independent of migration files.  Everything is
    rolled back / dropped after each test.
    """
    engine = _make_sqlite_engine()
    Base.metadata.create_all(engine)

    TestSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def app_client():
    """Yield a FastAPI TestClient backed by an in-memory SQLite database.

    The FastAPI `get_db` dependency is overridden so every request during a
    test uses the same isolated SQLite session.  This lets us test the full
    HTTP stack (routing, auth middleware, response serialisation) without
    touching PostgreSQL.

    Yields a (client, session) tuple so tests can also insert data directly
    via the session when needed.
    """
    engine = _make_sqlite_engine()
    Base.metadata.create_all(engine)

    TestSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Clean up overrides and drop tables after the test.
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()

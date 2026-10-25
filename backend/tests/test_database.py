"""Tests for the database session setup and cleanup behavior."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, SessionLocal, engine
from app.models import User


class TestDatabaseEngine:
    """Verify the database engine and Base are configured."""

    def test_base_is_declarative(self):
        """Base should be a DeclarativeBase subclass."""
        from sqlalchemy.orm import DeclarativeBase

        assert issubclass(Base, DeclarativeBase)

    def test_base_has_model_metadata(self):
        """Base.metadata should contain all model tables."""
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "users",
            "resumes",
            "job_descriptions",
            "job_matches",
            "skill_gaps",
            "interview_sessions",
            "job_applications",
        }
        assert expected.issubset(table_names)


class TestSessionIsolation:
    """Verify that test database sessions are isolated."""

    def test_session_rolls_back_data(self, db_session):
        """Data added in one test should not appear in another."""
        user = User(
            email="isolation@example.com",
            full_name="Isolation Test",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()

        # The fixture will clean up after this test.
        assert db_session.query(User).count() == 1

    def test_second_test_has_clean_db(self, db_session):
        """This test runs after the one above — data should not persist."""
        # If isolation is working, there should be zero users.
        assert db_session.query(User).count() == 0


class TestGetDbDependency:
    """Test the FastAPI get_db dependency generator."""

    def test_get_db_yields_session(self):
        """get_db should yield a database session."""
        gen = get_db()
        session = next(gen)
        assert session is not None
        # Clean up
        try:
            next(gen)
        except StopIteration:
            pass

    def test_get_db_closes_session(self):
        """get_db should close the session when the generator is exhausted.

        We verify the generator pattern works: it yields a session, and
        when the generator is exhausted, the finally block runs session.close().
        """
        gen = get_db()
        session = next(gen)
        assert session is not None

        # Exhaust the generator — the finally block calls session.close()
        try:
            next(gen)
            assert False, "Generator should have been exhausted"
        except StopIteration:
            pass  # Expected — generator finished cleanly

        # After close(), the session should not be in a transaction.
        assert session.in_transaction() is False

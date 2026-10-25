"""Tests for Alembic configuration and migration behavior.

These tests verify that:
1. The alembic.ini file exists and is configured correctly.
2. The migration env.py loads model metadata.
3. The initial migration file creates all expected tables.
4. The migration applies successfully to a temporary SQLite database.
"""

import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect


# Path to the backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


class TestAlembicConfig:
    """Verify Alembic configuration files exist and are valid."""

    def test_alembic_ini_exists(self):
        """alembic.ini should exist in the backend directory."""
        assert ALEMBIC_INI.is_file()

    def test_alembic_env_py_exists(self):
        """alembic/env.py should exist."""
        env_py = BACKEND_DIR / "alembic" / "env.py"
        assert env_py.is_file()

    def test_alembic_versions_dir_exists(self):
        """alembic/versions/ directory should exist."""
        versions_dir = BACKEND_DIR / "alembic" / "versions"
        assert versions_dir.is_dir()

    def test_script_template_exists(self):
        """alembic/script.py.mako should exist."""
        mako = BACKEND_DIR / "alembic" / "script.py.mako"
        assert mako.is_file()

    def test_alembic_script_directory_loads(self):
        """The ScriptDirectory should load without errors."""
        cfg = Config(str(ALEMBIC_INI))
        script_dir = ScriptDirectory.from_config(cfg)
        assert script_dir is not None


class TestInitialMigration:
    """Verify the initial migration file exists and contains all tables."""

    def test_migration_files_exist(self):
        """At least one migration file should exist."""
        versions_dir = BACKEND_DIR / "alembic" / "versions"
        migration_files = list(versions_dir.glob("*.py"))
        assert len(migration_files) > 0, "No migration files found"

    def test_initial_migration_creates_all_tables(self):
        """The initial migration should create all 7 application tables."""
        versions_dir = BACKEND_DIR / "alembic" / "versions"
        migration_files = list(versions_dir.glob("*.py"))
        combined_content = ""
        for f in migration_files:
            combined_content += f.read_text(encoding="utf-8")

        expected_tables = [
            "users",
            "resumes",
            "job_descriptions",
            "job_matches",
            "skill_gaps",
            "interview_sessions",
            "job_applications",
        ]
        for table in expected_tables:
            assert f"create_table('{table}'" in combined_content, (
                f"Migration does not create table '{table}'"
            )


class TestMigrationAppliesToSQLite:
    """Verify the migration applies successfully to a temporary database."""

    @pytest.fixture()
    def temp_db_url(self, tmp_path):
        """Provide a temporary SQLite database file URL."""
        db_file = tmp_path / "test_migration.db"
        return f"sqlite:///{db_file}"

    def test_migration_applies_and_creates_tables(self, temp_db_url, monkeypatch):
        """Running `alembic upgrade head` should create all tables."""
        # Set DATABASE_URL environment variable for alembic/env.py
        monkeypatch.setenv("DATABASE_URL", temp_db_url)

        cfg = Config(str(ALEMBIC_INI))
        # Override the URL in the config as well
        cfg.set_main_option("sqlalchemy.url", temp_db_url)

        # Run the migration
        command.upgrade(cfg, "head")

        # Verify all tables were created
        engine = create_engine(temp_db_url)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        engine.dispose()

        expected = [
            "users",
            "resumes",
            "job_descriptions",
            "job_matches",
            "skill_gaps",
            "interview_sessions",
            "job_applications",
        ]
        for table in expected:
            assert table in table_names, f"Table '{table}' was not created by migration"

    def test_migration_can_downgrade(self, temp_db_url, monkeypatch):
        """Running `alembic downgrade base` should remove all tables."""
        monkeypatch.setenv("DATABASE_URL", temp_db_url)

        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("sqlalchemy.url", temp_db_url)

        # First upgrade
        command.upgrade(cfg, "head")

        # Then downgrade to base (remove all)
        command.downgrade(cfg, "base")

        # Verify application tables are gone
        engine = create_engine(temp_db_url)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        engine.dispose()

        expected_gone = [
            "users",
            "resumes",
            "job_descriptions",
            "job_matches",
            "skill_gaps",
            "interview_sessions",
            "job_applications",
        ]
        for table in expected_gone:
            assert table not in table_names, f"Table '{table}' should have been removed"

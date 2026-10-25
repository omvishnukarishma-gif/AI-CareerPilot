"""Alembic migration environment.

Reads the database URL from the DATABASE_URL environment variable (falling
back to app.config.settings) and imports all model modules so Alembic can
auto-detect schema changes.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import settings so the URL comes from environment variables, not alembic.ini.
from app.config import settings
# Import Base and all models so their metadata is available for autogenerate.
from app.database import Base
from app.models import (  # noqa: F401 — imported for side effects (model registration)
    User,
    Resume,
    JobDescription,
    JobMatch,
    SkillGap,
    InterviewSession,
    JobApplication,
)

# Alembic Config object.
config = context.config

# Read the database URL from the environment first (so tests can override it),
# then fall back to the settings value.
db_url = os.environ.get("DATABASE_URL", settings.database_url)
config.set_main_option("sqlalchemy.url", db_url)

# Configure Python logging from alembic.ini if the section exists.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """

    url = db_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Connects to the database and applies migrations.
    """

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

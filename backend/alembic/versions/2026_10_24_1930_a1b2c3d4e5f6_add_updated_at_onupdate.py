"""add updated_at onupdate

Revision ID: a1b2c3d4e5f6
Revises: b726251a80da
Create Date: 2026-10-24 19:30:00.000000

Documents that updated_at columns are now managed by SQLAlchemy ORM's
onupdate hook (onupdate=func.now()), which emits CURRENT_TIMESTAMP in
every UPDATE statement for any model that uses TimestampMixin.

No schema change is required — the column already exists from the initial
migration.  This migration records the behaviour change in the migration
history so operators can track it.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b726251a80da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # updated_at is now managed by SQLAlchemy ORM onupdate=func.now().
    # For every UPDATE statement the ORM emits, it explicitly includes
    #   updated_at = CURRENT_TIMESTAMP
    # This works correctly for both PostgreSQL and SQLite.
    # No schema change is needed — the column definition is unchanged.
    pass


def downgrade() -> None:
    # Nothing to undo — the column existed before this migration.
    pass

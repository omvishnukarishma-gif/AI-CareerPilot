"""Shared base class for all ORM models.

Provides a common set of timestamp columns so every table records
when it was created and last updated, without repeating the same
column definitions in every model file.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns to a model.

    Both columns are managed automatically by the database:
    - created_at is set once when the row is inserted.
    - updated_at is refreshed on every UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


__all__ = ["Base", "TimestampMixin"]

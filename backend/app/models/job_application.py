"""JobApplication model — tracks a user's job application status.

A standalone record (linked only to the user) that tracks which
companies the user has applied to, the role, current status, and notes.
"""

from sqlalchemy import String, Text, ForeignKey, DateTime
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JobApplication(TimestampMixin, Base):
    """A job application tracked by a user.

    Fields:
        user_id:       FK to users.id (owner).
        company_name:  Name of the company applied to.
        role_title:    Title of the role.
        status:        Application status enum-like string:
                       "applied", "interviewing", "offer", "rejected", "archived".
        job_url:       Optional URL to the job posting.
        notes:         Free-text notes about the application.
        deadline:      Optional application or interview deadline.

    Relationships:
        user: Belongs to one User.
    """

    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="applied", nullable=False, index=True)
    job_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="job_applications")

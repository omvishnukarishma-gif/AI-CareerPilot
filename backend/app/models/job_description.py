"""JobDescription model — a job posting a user wants to compare against.

A user pastes (or links) a job description, and the platform compares
their resume against it to identify matched/missing skills.
"""

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JobDescription(TimestampMixin, Base):
    """A job description saved by a user for comparison.

    Fields:
        user_id:          FK to users.id (owner).
        title:            Job title (e.g., "Senior Python Developer").
        company:          Company name (optional — may be unknown).
        description_text: Full text of the job description.

    Relationships:
        user:         Belongs to one User.
        job_matches:  One job description → many JobMatch comparisons.
        skill_gaps:   One job description → many SkillGap analyses.
        interview_sessions: One job description → many InterviewSession (optional link).
    """

    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="job_descriptions")
    job_matches: Mapped[list["JobMatch"]] = relationship(
        back_populates="job_description", cascade="all, delete-orphan"
    )
    skill_gaps: Mapped[list["SkillGap"]] = relationship(
        back_populates="job_description", cascade="all, delete-orphan"
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="job_description"
    )

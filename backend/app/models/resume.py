"""Resume model — a user's uploaded resume and its AI-parsed data.

Each user can have multiple resumes (e.g., tailored for different roles).
The parsed_data column stores the structured output from the AI resume
parser as JSON (skills, experience, education, summary).
"""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Resume(TimestampMixin, Base):
    """A resume uploaded by a user.

    Fields:
        user_id:      FK to users.id (owner).
        file_name:    Original file name (e.g., "john_resume.pdf").
        content_text: Raw text extracted from the resume file.
        parsed_data:  JSON column storing AI-extracted structured data
                      (skills, work experience, education, etc.).

    Relationships:
        user:           Belongs to one User.
        job_matches:    One resume → many JobMatch comparisons.
        skill_gaps:     One resume → many SkillGap analyses.
        interview_sessions: One resume → many InterviewSession (optional link).
    """

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="resumes")
    job_matches: Mapped[list["JobMatch"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    skill_gaps: Mapped[list["SkillGap"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="resume"
    )

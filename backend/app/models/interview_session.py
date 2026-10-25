"""InterviewSession model — a mock interview session.

Stores the AI-generated interview questions and the full transcript
of the user's practice session.  Optionally linked to a resume and/or
job description so questions can be tailored to a specific role.
"""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InterviewSession(TimestampMixin, Base):
    """A mock interview practice session.

    Fields:
        user_id:              FK to users.id (owner).
        resume_id:            FK to resumes.id (optional — tailors questions).
        job_description_id:    FK to job_descriptions.id (optional — tailors questions).
        role_target:          The target role (e.g., "Backend Engineer").
        status:               Session status: "started", "completed".
        questions:            JSON list of AI-generated questions.
        transcript:           JSON list of {question, answer, feedback} entries.

    Relationships:
        user:            Belongs to one User.
        resume:          Optionally belongs to one Resume.
        job_description: Optionally belongs to one JobDescription.
    """

    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_description_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role_target: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="started", nullable=False)
    questions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    transcript: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="interview_sessions")
    resume: Mapped["Resume | None"] = relationship(back_populates="interview_sessions")
    job_description: Mapped["JobDescription | None"] = relationship(
        back_populates="interview_sessions"
    )

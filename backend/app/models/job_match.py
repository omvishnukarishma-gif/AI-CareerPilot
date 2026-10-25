"""JobMatch model — a comparison between a resume and a job description.

When a user clicks "Match my resume", the platform compares a specific
resume against a specific job description and stores the result here.
The match_score is a 0-100 value indicating how well the resume fits.
"""

from sqlalchemy import JSON, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JobMatch(TimestampMixin, Base):
    """The result of comparing a resume to a job description.

    Fields:
        resume_id:           FK to resumes.id.
        job_description_id:  FK to job_descriptions.id.
        match_score:         0.0 to 100.0 — overall fit score.
        matched_skills:      JSON list of skills present in both resume and job.
        missing_skills:      JSON list of skills required by the job but
                              missing from the resume.

    Relationships:
        resume:          Belongs to one Resume.
        job_description: Belongs to one JobDescription.
        skill_gap:       One-to-one with SkillGap (the detailed analysis).
    """

    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_description_id: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matched_skills: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    missing_skills: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    resume: Mapped["Resume"] = relationship(back_populates="job_matches")
    job_description: Mapped["JobDescription"] = relationship(back_populates="job_matches")
    skill_gap: Mapped["SkillGap | None"] = relationship(
        back_populates="job_match", uselist=False, cascade="all, delete-orphan"
    )

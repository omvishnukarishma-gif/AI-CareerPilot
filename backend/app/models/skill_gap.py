"""SkillGap model — detailed skill gap analysis for a job match.

While JobMatch stores the high-level match score, SkillGap stores the
detailed breakdown: which skills are missing, which are matched, and
what the AI recommends to close the gap.
"""

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SkillGap(TimestampMixin, Base):
    """Detailed skill gap analysis linked to a JobMatch.

    Fields:
        job_match_id:        FK to job_matches.id — one-to-one relationship.
        resume_id:           FK to resumes.id (for direct queries by resume).
        job_description_id:   FK to job_descriptions.id (for direct queries).
        matched_skills:      JSON list of matched skills with details.
        missing_skills:      JSON list of missing skills with details.
        recommendations:     JSON list of AI-generated learning recommendations.

    Relationships:
        job_match:       Belongs to one JobMatch (one-to-one).
        resume:          Belongs to one Resume.
        job_description: Belongs to one JobDescription.
    """

    __tablename__ = "skill_gaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_match_id: Mapped[int] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_description_id: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matched_skills: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    missing_skills: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    job_match: Mapped["JobMatch"] = relationship(back_populates="skill_gap")
    resume: Mapped["Resume"] = relationship(back_populates="skill_gaps")
    job_description: Mapped["JobDescription"] = relationship(back_populates="skill_gaps")

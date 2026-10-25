"""User model — represents a registered user of the platform.

Every other record (resumes, job descriptions, interviews, applications)
belongs to a user via a foreign key.  This is the ownership anchor that
authorization checks will use in later phases.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """A registered user.

    Fields:
        email:      Unique email address — used for login.
        full_name:  Display name shown in the UI.
        is_active:  Soft-delete flag (False = account disabled).

    Relationships:
        resumes:            One user → many resumes
        job_descriptions:   One user → many job descriptions
        interview_sessions: One user → many interview sessions
        job_applications:   One user → many job applications
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Password hashing will be added in the authentication phase.
    # For now we store a placeholder column so the schema is ready.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    job_descriptions: Mapped[list["JobDescription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    job_applications: Mapped[list["JobApplication"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

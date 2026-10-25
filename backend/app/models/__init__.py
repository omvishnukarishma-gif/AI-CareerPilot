"""SQLAlchemy ORM models.

All model classes are exported from this package so they can be imported
in one line:

    from app.models import User, Resume, JobDescription, ...
"""

from app.models.user import User
from app.models.resume import Resume
from app.models.job_description import JobDescription
from app.models.job_match import JobMatch
from app.models.skill_gap import SkillGap
from app.models.interview_session import InterviewSession
from app.models.job_application import JobApplication

__all__ = [
    "User",
    "Resume",
    "JobDescription",
    "JobMatch",
    "SkillGap",
    "InterviewSession",
    "JobApplication",
]

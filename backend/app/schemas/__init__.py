"""Schema package for API request/response models."""

from app.schemas.resume import ResumeDetailResponse, ResumeResponse
from app.schemas.job_description import (
    JobDescriptionCreate,
    JobDescriptionDetailResponse,
    JobDescriptionResponse,
)
from app.schemas.match import (
    MatchCreate,
    MatchDetailResponse,
    MatchResponse,
    SkillGapResponse,
)
from app.schemas.interview import (
    AnswerSubmit,
    FeedbackOut,
    InterviewSessionCreate,
    InterviewSessionDetailResponse,
    InterviewSessionResponse,
    QuestionOut,
    TranscriptEntry,
)
from app.schemas.job_application import (
    JobApplicationCreate,
    JobApplicationResponse,
    JobApplicationUpdate,
)

__all__ = [
    "ResumeResponse",
    "ResumeDetailResponse",
    "JobDescriptionCreate",
    "JobDescriptionResponse",
    "JobDescriptionDetailResponse",
    "MatchCreate",
    "MatchResponse",
    "MatchDetailResponse",
    "SkillGapResponse",
    "AnswerSubmit",
    "FeedbackOut",
    "InterviewSessionCreate",
    "InterviewSessionDetailResponse",
    "InterviewSessionResponse",
    "QuestionOut",
    "TranscriptEntry",
    "JobApplicationCreate",
    "JobApplicationUpdate",
    "JobApplicationResponse",
]

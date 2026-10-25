"""Pydantic schemas for interview-session endpoints.

Covers request validation and response shapes for:
  POST   /api/v1/interview-sessions                → create / start a session
  GET    /api/v1/interview-sessions                → list user's sessions
  GET    /api/v1/interview-sessions/{id}           → get full session detail
  POST   /api/v1/interview-sessions/{id}/answers   → submit an answer
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------


class QuestionOut(BaseModel):
    """A single interview question as returned by the API.

    expected_keywords is intentionally omitted — it is an internal
    implementation detail of the evaluator and should not be sent to
    the client.
    """

    text: str
    category: str
    skill_ref: str | None = None


class FeedbackOut(BaseModel):
    """Structured feedback for a single answer."""

    score: float
    strengths: list[str]
    improvements: list[str]
    note: str


class TranscriptEntry(BaseModel):
    """One answered question in the session transcript.

    question_index: 0-based index into the questions list.
    question_text:  Snapshot of the question text (for readability).
    answer:         The user's raw answer text.
    feedback:       Evaluation feedback from the evaluator.
    """

    question_index: int
    question_text: str
    answer: str
    feedback: FeedbackOut


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class InterviewSessionCreate(BaseModel):
    """Request body for starting a new interview session.

    role_target:         The role the user is practising for.
                         Required — used to select role-specific questions.
    job_description_id:  Optional FK to one of the user's job descriptions.
                         When supplied, the JD text is used to generate
                         skill-gap questions.
    resume_id:           Optional FK to one of the user's resumes.
                         When supplied and a JD is also given, questions
                         focus on skills missing from the resume.
    """

    role_target: str = Field(min_length=2, max_length=255)
    job_description_id: int | None = Field(default=None, gt=0)
    resume_id: int | None = Field(default=None, gt=0)


class AnswerSubmit(BaseModel):
    """Request body for submitting an answer to one question.

    question_index: Which question (0-based) the user is answering.
    answer:         The raw answer text.  At least 3 characters so empty
                    submissions are rejected at the validation layer.
    """

    question_index: int = Field(ge=0)
    answer: str = Field(min_length=3, max_length=5_000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class InterviewSessionResponse(BaseModel):
    """Safe session representation used in the list endpoint.

    Omits the full questions list and transcript to keep list payloads lean.
    """

    id: int
    user_id: int
    role_target: str
    status: str
    job_description_id: int | None
    resume_id: int | None
    question_count: int
    answers_given: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}


class InterviewSessionDetailResponse(BaseModel):
    """Full session detail including questions and transcript."""

    id: int
    user_id: int
    role_target: str
    status: str
    job_description_id: int | None
    resume_id: int | None
    questions: list[QuestionOut]
    transcript: list[TranscriptEntry]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}

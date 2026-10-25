"""Interview-sessions router — start, answer, complete, and list sessions.

All endpoints are mounted under /api/v1/interview-sessions (via main.py prefix).

Endpoints
---------
POST   /interview-sessions                 → start a new session
GET    /interview-sessions                 → list the current user's sessions
GET    /interview-sessions/{id}            → get full session detail
POST   /interview-sessions/{id}/answers    → submit one answer

Security
--------
Every endpoint requires a valid Bearer token.  Ownership is enforced by
filtering on user_id — users can never read or modify each other's sessions.
Referenced resumes and job descriptions must also belong to the requesting
user; mismatched or non-existent records return 404 to prevent enumeration.

State transitions
-----------------
  started   → (answers submitted one at a time until all questions answered)
  started   → completed   (automatically when the last answer is submitted)

A ``completed`` session is read-only; submitting further answers returns 409.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.interviewer import Question, evaluate_answer, generate_questions
from app.core.llm import get_llm_provider
from app.database import get_db
from app.models import InterviewSession, JobDescription, Resume, User
from app.schemas.interview import (
    AnswerSubmit,
    FeedbackOut,
    InterviewSessionCreate,
    InterviewSessionDetailResponse,
    InterviewSessionResponse,
    QuestionOut,
    TranscriptEntry,
)

router = APIRouter(prefix="/interview-sessions", tags=["interview-sessions"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _session_to_response(session: InterviewSession) -> InterviewSessionResponse:
    """Convert a session ORM row to the lean list-response schema."""
    questions_raw: list[dict] = session.questions or []
    transcript_raw: list[dict] = session.transcript or []
    return InterviewSessionResponse(
        id=session.id,
        user_id=session.user_id,
        role_target=session.role_target,
        status=session.status,
        job_description_id=session.job_description_id,
        resume_id=session.resume_id,
        question_count=len(questions_raw),
        answers_given=len(transcript_raw),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _session_to_detail(session: InterviewSession) -> InterviewSessionDetailResponse:
    """Convert a session ORM row to the full detail schema."""
    questions_raw: list[dict] = session.questions or []
    transcript_raw: list[dict] = session.transcript or []

    questions_out = [
        QuestionOut(
            text=q["text"],
            category=q["category"],
            skill_ref=q.get("skill_ref"),
        )
        for q in questions_raw
    ]

    transcript_out = [
        TranscriptEntry(
            question_index=entry["question_index"],
            question_text=entry["question_text"],
            answer=entry["answer"],
            feedback=FeedbackOut(**entry["feedback"]),
        )
        for entry in transcript_raw
    ]

    return InterviewSessionDetailResponse(
        id=session.id,
        user_id=session.user_id,
        role_target=session.role_target,
        status=session.status,
        job_description_id=session.job_description_id,
        resume_id=session.resume_id,
        questions=questions_out,
        transcript=transcript_out,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=InterviewSessionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new interview session",
    description=(
        "Create a new interview-practice session for the authenticated user. "
        "Generates a tailored set of questions based on the role, optional job "
        "description, and optional resume. "
        "Requires a valid Bearer token."
    ),
)
def create_interview_session(
    payload: InterviewSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionDetailResponse:
    """Start a new interview session and generate questions.

    Ownership of the referenced resume and job description is verified before
    the session is created.  If either does not exist or belongs to another
    user the endpoint returns 404.
    """
    # --- Optionally verify resume ownership ---
    resume_text: str | None = None
    if payload.resume_id is not None:
        resume = (
            db.query(Resume)
            .filter(
                Resume.id == payload.resume_id,
                Resume.user_id == current_user.id,
            )
            .first()
        )
        if resume is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found.",
            )
        resume_text = resume.content_text

    # --- Optionally verify job description ownership ---
    jd_text: str | None = None
    if payload.job_description_id is not None:
        jd = (
            db.query(JobDescription)
            .filter(
                JobDescription.id == payload.job_description_id,
                JobDescription.user_id == current_user.id,
            )
            .first()
        )
        if jd is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job description not found.",
            )
        jd_text = jd.description_text

    # --- Generate questions ---
    questions = generate_questions(
        role_target=payload.role_target,
        jd_text=jd_text,
        resume_text=resume_text,
    )

    # --- Persist ---
    session = InterviewSession(
        user_id=current_user.id,
        resume_id=payload.resume_id,
        job_description_id=payload.job_description_id,
        role_target=payload.role_target.strip(),
        status="started",
        questions=[q.to_dict() for q in questions],
        transcript=[],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return _session_to_detail(session)


@router.get(
    "",
    response_model=list[InterviewSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List current user's interview sessions",
    description=(
        "Return all interview sessions belonging to the authenticated user, "
        "ordered by creation date (newest first). "
        "Omits the full question list and transcript to keep payloads lean. "
        "Requires a valid Bearer token."
    ),
)
def list_interview_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InterviewSessionResponse]:
    """Return all sessions owned by the current user."""
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
        .all()
    )
    return [_session_to_response(s) for s in sessions]


@router.get(
    "/{session_id}",
    response_model=InterviewSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get one interview session (full detail)",
    description=(
        "Return the full detail for a single interview session, including "
        "all questions and the answer transcript. "
        "Returns 404 if the record does not exist or belongs to a different "
        "user. Requires a valid Bearer token."
    ),
)
def get_interview_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionDetailResponse:
    """Return one session owned by the current user."""
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found.",
        )
    return _session_to_detail(session)


@router.post(
    "/{session_id}/answers",
    response_model=InterviewSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit an answer to one question",
    description=(
        "Submit the user's answer to the question at `question_index` in the "
        "session's question list. The evaluator scores the answer and appends "
        "the result to the session transcript. "
        "When the last question is answered the session status changes to "
        "'completed'. Subsequent submissions on a completed session return 409. "
        "Requires a valid Bearer token."
    ),
)
def submit_answer(
    session_id: int,
    payload: AnswerSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionDetailResponse:
    """Evaluate one answer and append it to the session transcript.

    Rules:
    - The session must be owned by the requesting user (404 otherwise).
    - The session must be in 'started' status (409 if completed).
    - question_index must be within bounds (422 if not).
    - Each question can only be answered once (409 if already answered).
    """
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found.",
        )

    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This interview session is already completed.",
        )

    questions_raw: list[dict] = session.questions or []
    n_questions = len(questions_raw)

    if payload.question_index >= n_questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"question_index {payload.question_index} is out of range. "
                f"This session has {n_questions} question(s) (indices 0–{n_questions - 1})."
            ),
        )

    transcript: list[dict] = list(session.transcript or [])

    # Check whether this question has already been answered
    answered_indices = {entry["question_index"] for entry in transcript}
    if payload.question_index in answered_indices:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question {payload.question_index} has already been answered.",
        )

    # Evaluate the answer (deterministic)
    question_data = questions_raw[payload.question_index]
    question = Question.from_dict(question_data)
    evaluation = evaluate_answer(question, payload.answer)

    # --- Optional LLM-enhanced feedback ---
    # Falls back to deterministic result if no provider or on failure.
    feedback_dict = evaluation.to_dict()
    provider = get_llm_provider()
    if provider is not None:
        try:
            llm_feedback = provider.enhance_feedback(
                question.text,
                question.category,
                payload.answer,
                evaluation.score,
            )
            if llm_feedback is not None:
                feedback_dict = {
                    "score": llm_feedback.score,
                    "strengths": llm_feedback.strengths,
                    "improvements": llm_feedback.improvements,
                    "note": llm_feedback.note,
                }
        except Exception:  # noqa: BLE001
            logger.warning(
                "LLM enhance_feedback failed; using deterministic fallback"
            )

    # Append to transcript
    transcript.append(
        {
            "question_index": payload.question_index,
            "question_text": question.text,
            "answer": payload.answer,
            "feedback": feedback_dict,
        }
    )

    # Determine new status — complete when all questions answered
    new_status = "completed" if len(transcript) >= n_questions else "started"

    # Persist — SQLAlchemy does not detect in-place mutation of JSON columns
    # on all backends; replace the column value to guarantee the update is
    # tracked.
    session.transcript = transcript
    session.status = new_status
    db.add(session)
    db.commit()
    db.refresh(session)

    return _session_to_detail(session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an interview session",
    description=(
        "Permanently delete an interview session and its transcript. "
        "Returns 404 if the session does not exist or belongs to a different "
        "user. Requires a valid Bearer token."
    ),
)
def delete_interview_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete one interview session owned by the current user."""
    session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found.",
        )
    db.delete(session)
    db.commit()

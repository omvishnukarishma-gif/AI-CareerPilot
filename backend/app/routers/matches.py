"""Matches router — run resume–job matching and retrieve results.

All endpoints are mounted under /api/v1/matches (via main.py prefix).

Endpoints:
    POST  /matches       → create a new match (runs scoring + skill-gap analysis)
    GET   /matches       → list the current user's matches
    GET   /matches/{id}  → get one match with its skill-gap detail

Security: every endpoint requires a valid Bearer token.  Both the resume
and the job description must be owned by the requesting user; mismatched or
non-existent records return 404 so that IDs cannot be enumerated.

Matching algorithm: see app.core.matcher for documentation.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.llm import get_llm_provider
from app.core.matcher import compute_match
from app.database import get_db

logger = logging.getLogger(__name__)
from app.models import JobDescription, JobMatch, Resume, SkillGap, User
from app.schemas.match import (
    MatchCreate,
    MatchDetailResponse,
    MatchResponse,
    SkillGapResponse,
)

router = APIRouter(prefix="/matches", tags=["matches"])


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _match_to_response(match: JobMatch) -> MatchResponse:
    """Convert a JobMatch ORM row to a MatchResponse schema."""
    return MatchResponse(
        id=match.id,
        resume_id=match.resume_id,
        job_description_id=match.job_description_id,
        match_score=match.match_score,
        matched_skills=match.matched_skills or [],
        missing_skills=match.missing_skills or [],
        created_at=match.created_at,
        updated_at=match.updated_at,
    )


def _match_to_detail(match: JobMatch) -> MatchDetailResponse:
    """Convert a JobMatch ORM row (with loaded skill_gap) to MatchDetailResponse."""
    sg_response: SkillGapResponse | None = None
    if match.skill_gap is not None:
        sg = match.skill_gap
        sg_response = SkillGapResponse(
            id=sg.id,
            matched_skills=sg.matched_skills or [],
            missing_skills=sg.missing_skills or [],
            recommendations=sg.recommendations or [],
            created_at=sg.created_at,
            updated_at=sg.updated_at,
        )

    jd_title = match.job_description.title if match.job_description else ""
    resume_name = match.resume.file_name if match.resume else ""

    return MatchDetailResponse(
        id=match.id,
        resume_id=match.resume_id,
        job_description_id=match.job_description_id,
        match_score=match.match_score,
        matched_skills=match.matched_skills or [],
        missing_skills=match.missing_skills or [],
        created_at=match.created_at,
        updated_at=match.updated_at,
        skill_gap=sg_response,
        job_description_title=jd_title,
        resume_file_name=resume_name,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=MatchDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a resume–job match",
    description=(
        "Compute the match score between one of the user's resumes and one "
        "of their job descriptions. Persists the result and a skill-gap "
        "analysis. Both records must belong to the authenticated user. "
        "Requires a valid Bearer token."
    ),
)
def create_match(
    payload: MatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchDetailResponse:
    """Run the matching algorithm and persist results.

    Ownership of both resume and job description is verified before scoring.
    If either record does not exist or belongs to another user the endpoint
    returns 404 so IDs cannot be enumerated.
    """
    # --- Verify resume ownership ---
    resume = (
        db.query(Resume)
        .filter(Resume.id == payload.resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )

    # --- Verify job description ownership ---
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

    # --- Run the matcher ---
    result = compute_match(resume.content_text, jd.description_text)

    # --- Optional LLM-enhanced recommendations ---
    # Falls back to deterministic recommendations if no provider or on failure.
    final_recommendations = result.recommendations
    provider = get_llm_provider()
    if provider is not None:
        try:
            llm_result = provider.enhance_recommendations(
                result.matched_skills,
                result.missing_skills,
                resume.content_text,
                jd.description_text,
            )
            if llm_result is not None:
                final_recommendations = llm_result.recommendations
        except Exception:  # noqa: BLE001
            logger.warning(
                "LLM enhance_recommendations failed; using deterministic fallback"
            )

    # --- Persist JobMatch ---
    match = JobMatch(
        resume_id=resume.id,
        job_description_id=jd.id,
        match_score=result.score,
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
    )
    db.add(match)
    db.flush()  # obtain match.id before creating SkillGap

    # --- Persist SkillGap ---
    skill_gap = SkillGap(
        job_match_id=match.id,
        resume_id=resume.id,
        job_description_id=jd.id,
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
        recommendations=final_recommendations,
    )
    db.add(skill_gap)
    db.commit()
    db.refresh(match)

    return _match_to_detail(match)


@router.get(
    "",
    response_model=list[MatchResponse],
    status_code=status.HTTP_200_OK,
    summary="List current user's matches",
    description=(
        "Return all matches belonging to the authenticated user, ordered by "
        "creation date (newest first). Does not include skill-gap detail. "
        "Requires a valid Bearer token."
    ),
)
def list_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MatchResponse]:
    """Return all matches for resumes owned by the current user."""
    matches = (
        db.query(JobMatch)
        .join(Resume, JobMatch.resume_id == Resume.id)
        .filter(Resume.user_id == current_user.id)
        .order_by(JobMatch.created_at.desc(), JobMatch.id.desc())
        .all()
    )
    return [_match_to_response(m) for m in matches]


@router.get(
    "/{match_id}",
    response_model=MatchDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get one match with skill-gap detail",
    description=(
        "Return the full detail for a single match, including the skill-gap "
        "analysis. Returns 404 if the record does not exist or belongs to a "
        "different user. Requires a valid Bearer token."
    ),
)
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchDetailResponse:
    """Return one match owned (via its resume) by the current user."""
    match = (
        db.query(JobMatch)
        .join(Resume, JobMatch.resume_id == Resume.id)
        .filter(JobMatch.id == match_id, Resume.user_id == current_user.id)
        .first()
    )
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )
    return _match_to_detail(match)

"""Job-description router — create, list, retrieve, update, and delete job descriptions.

All endpoints are mounted under /api/v1/job-descriptions (via main.py prefix).

Endpoints:
    POST   /job-descriptions        → create a new job description
    GET    /job-descriptions        → list the current user's job descriptions
    GET    /job-descriptions/{id}   → get one job description (with full text)
    PUT    /job-descriptions/{id}   → update (full replacement) a job description
    DELETE /job-descriptions/{id}   → delete a job description

Security: every endpoint requires a valid Bearer token.  Ownership is
enforced by filtering on user_id — users can never see or modify each
other's job descriptions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import JobDescription, User
from app.schemas.job_description import (
    JobDescriptionCreate,
    JobDescriptionDetailResponse,
    JobDescriptionResponse,
)

router = APIRouter(prefix="/job-descriptions", tags=["job-descriptions"])


@router.post(
    "",
    response_model=JobDescriptionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job description",
    description=(
        "Save a job description for later matching against a resume. "
        "Returns the full detail including description_text. "
        "Requires a valid Bearer token."
    ),
)
def create_job_description(
    payload: JobDescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionDetailResponse:
    """Persist a new job description owned by the current user."""
    jd = JobDescription(
        user_id=current_user.id,
        title=payload.title.strip(),
        company=payload.company.strip() if payload.company else None,
        description_text=payload.description_text,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return JobDescriptionDetailResponse.model_validate(jd)


@router.get(
    "",
    response_model=list[JobDescriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="List current user's job descriptions",
    description=(
        "Return all job descriptions belonging to the authenticated user, "
        "ordered by creation date (newest first). "
        "Excludes description_text to keep payloads lean. "
        "Requires a valid Bearer token."
    ),
)
def list_job_descriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobDescriptionResponse]:
    """Return all job descriptions owned by the current user."""
    jds = (
        db.query(JobDescription)
        .filter(JobDescription.user_id == current_user.id)
        .order_by(JobDescription.created_at.desc(), JobDescription.id.desc())
        .all()
    )
    return [JobDescriptionResponse.model_validate(jd) for jd in jds]


@router.get(
    "/{jd_id}",
    response_model=JobDescriptionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get one job description (with full text)",
    description=(
        "Return the full detail for a single job description, including "
        "description_text. Returns 404 if the record does not exist or "
        "belongs to a different user. Requires a valid Bearer token."
    ),
)
def get_job_description(
    jd_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionDetailResponse:
    """Return one job description owned by the current user.

    Both non-existent IDs and IDs belonging to another user return 404 to
    prevent enumeration of other users' job descriptions.
    """
    jd = (
        db.query(JobDescription)
        .filter(
            JobDescription.id == jd_id,
            JobDescription.user_id == current_user.id,
        )
        .first()
    )
    if jd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found.",
        )
    return JobDescriptionDetailResponse.model_validate(jd)


@router.put(
    "/{jd_id}",
    response_model=JobDescriptionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a job description",
    description=(
        "Update an existing job description. "
        "All fields in the request body will replace the current values. "
        "Returns 404 if the record does not exist or belongs to a different user. "
        "Requires a valid Bearer token."
    ),
)
def update_job_description(
    jd_id: int,
    payload: JobDescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionDetailResponse:
    """Update one job description owned by the current user.

    This is a full replacement update (PUT) — all fields must be provided.
    Related job matches and skill gaps remain intact and still reference
    this job description, but their content reflects the OLD description text.
    """
    jd = (
        db.query(JobDescription)
        .filter(
            JobDescription.id == jd_id,
            JobDescription.user_id == current_user.id,
        )
        .first()
    )
    if jd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found.",
        )

    # Update all fields
    jd.title = payload.title.strip()
    jd.company = payload.company.strip() if payload.company else None
    jd.description_text = payload.description_text

    db.commit()
    db.refresh(jd)
    return JobDescriptionDetailResponse.model_validate(jd)


@router.delete(
    "/{jd_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job description",
    description=(
        "Permanently delete a job description. "
        "Related job matches and skill gaps are automatically deleted. "
        "Interview sessions that reference this job description will have their "
        "job_description_id set to NULL (the session is preserved). "
        "Returns 404 if the record does not exist or belongs to a different user. "
        "Requires a valid Bearer token."
    ),
)
def delete_job_description(
    jd_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete one job description owned by the current user.

    Related records are handled via SQLAlchemy cascade (job_matches,
    skill_gaps) and database FK constraints (interview_sessions SET NULL).
    """
    jd = (
        db.query(JobDescription)
        .filter(
            JobDescription.id == jd_id,
            JobDescription.user_id == current_user.id,
        )
        .first()
    )
    if jd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found.",
        )

    db.delete(jd)
    db.commit()

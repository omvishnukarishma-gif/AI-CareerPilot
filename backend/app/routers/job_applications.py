"""Job-application router — CRUD endpoints for tracking job applications.

All endpoints are mounted under /api/v1/job-applications (via main.py prefix).

Endpoints:
    POST   /job-applications        → create a new job application
    GET    /job-applications        → list the current user's job applications
    GET    /job-applications/{id}   → get one job application
    PUT    /job-applications/{id}   → update a job application
    DELETE /job-applications/{id}   → delete a job application

Security: every endpoint requires a valid Bearer token. Ownership is
enforced by filtering on user_id — users can never see or modify each
other's job applications.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import JobApplication, User
from app.schemas.job_application import (
    JobApplicationCreate,
    JobApplicationResponse,
    JobApplicationUpdate,
)

router = APIRouter(prefix="/job-applications", tags=["job-applications"])


@router.post(
    "",
    response_model=JobApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job application",
    description=(
        "Track a new job application. "
        "Returns the created record. "
        "Requires a valid Bearer token."
    ),
)
def create_job_application(
    payload: JobApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobApplicationResponse:
    """Persist a new job application owned by the current user."""
    app = JobApplication(
        user_id=current_user.id,
        company_name=payload.company_name.strip(),
        role_title=payload.role_title.strip(),
        status=payload.status,
        job_url=payload.job_url.strip() if payload.job_url else None,
        notes=payload.notes,
        deadline=payload.deadline,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return JobApplicationResponse.model_validate(app)


@router.get(
    "",
    response_model=list[JobApplicationResponse],
    status_code=status.HTTP_200_OK,
    summary="List current user's job applications",
    description=(
        "Return all job applications belonging to the authenticated user, "
        "ordered by creation date (newest first). "
        "Requires a valid Bearer token."
    ),
)
def list_job_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobApplicationResponse]:
    """Return all job applications owned by the current user."""
    apps = (
        db.query(JobApplication)
        .filter(JobApplication.user_id == current_user.id)
        .order_by(JobApplication.created_at.desc(), JobApplication.id.desc())
        .all()
    )
    return [JobApplicationResponse.model_validate(app) for app in apps]


@router.get(
    "/{app_id}",
    response_model=JobApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get one job application",
    description=(
        "Return full details for a single job application. "
        "Returns 404 if the record does not exist or belongs to a different user. "
        "Requires a valid Bearer token."
    ),
)
def get_job_application(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobApplicationResponse:
    """Return one job application owned by the current user.

    Both non-existent IDs and IDs belonging to another user return 404 to
    prevent enumeration of other users' applications.
    """
    app = (
        db.query(JobApplication)
        .filter(
            JobApplication.id == app_id,
            JobApplication.user_id == current_user.id,
        )
        .first()
    )
    if app is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job application not found.",
        )
    return JobApplicationResponse.model_validate(app)


@router.put(
    "/{app_id}",
    response_model=JobApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a job application",
    description=(
        "Update an existing job application. "
        "Only provided fields will be updated. "
        "Returns 404 if the record does not exist or belongs to a different user. "
        "Requires a valid Bearer token."
    ),
)
def update_job_application(
    app_id: int,
    payload: JobApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobApplicationResponse:
    """Update one job application owned by the current user.

    Only fields present in the payload (with non-None values) are updated.
    """
    app = (
        db.query(JobApplication)
        .filter(
            JobApplication.id == app_id,
            JobApplication.user_id == current_user.id,
        )
        .first()
    )
    if app is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job application not found.",
        )

    # Update only provided fields
    if payload.company_name is not None:
        app.company_name = payload.company_name.strip()
    if payload.role_title is not None:
        app.role_title = payload.role_title.strip()
    if payload.status is not None:
        app.status = payload.status
    if payload.job_url is not None:
        app.job_url = payload.job_url.strip() if payload.job_url else None
    if payload.notes is not None:
        app.notes = payload.notes
    if payload.deadline is not None:
        app.deadline = payload.deadline

    db.commit()
    db.refresh(app)
    return JobApplicationResponse.model_validate(app)


@router.delete(
    "/{app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job application",
    description=(
        "Permanently delete a job application. "
        "Returns 404 if the record does not exist or belongs to a different user. "
        "Requires a valid Bearer token."
    ),
)
def delete_job_application(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete one job application owned by the current user."""
    app = (
        db.query(JobApplication)
        .filter(
            JobApplication.id == app_id,
            JobApplication.user_id == current_user.id,
        )
        .first()
    )
    if app is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job application not found.",
        )

    db.delete(app)
    db.commit()

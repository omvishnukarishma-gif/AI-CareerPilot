"""Pydantic schemas for job application tracker endpoints.

Covers request validation and response shapes for:
  POST   /api/v1/job-applications       → create
  GET    /api/v1/job-applications        → list
  GET    /api/v1/job-applications/{id}   → detail
  PUT    /api/v1/job-applications/{id}   → update
  DELETE /api/v1/job-applications/{id}   → delete
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Allowed status values
# ---------------------------------------------------------------------------

ALLOWED_STATUSES = {"applied", "interviewing", "offer", "rejected", "archived"}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class JobApplicationCreate(BaseModel):
    """Request body for creating a job application.

    company_name: Name of the company (required).
    role_title:   Job title (required).
    status:       Application status (default: "applied").
    job_url:      Optional URL to the job posting.
    notes:        Optional free-text notes.
    deadline:     Optional application or interview deadline.
    """

    company_name: str = Field(min_length=1, max_length=255)
    role_title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="applied", max_length=50)
    job_url: str | None = Field(default=None, max_length=1024)
    notes: str | None = Field(default=None, max_length=50_000)
    deadline: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Ensure status is one of the allowed values."""
        if v not in ALLOWED_STATUSES:
            raise ValueError(
                f"Status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}. Got: {v}"
            )
        return v


class JobApplicationUpdate(BaseModel):
    """Request body for updating a job application.

    All fields are optional — only provided fields will be updated.
    """

    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    role_title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=50)
    job_url: str | None = Field(default=None, max_length=1024)
    notes: str | None = Field(default=None, max_length=50_000)
    deadline: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Ensure status is one of the allowed values if provided."""
        if v is not None and v not in ALLOWED_STATUSES:
            raise ValueError(
                f"Status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}. Got: {v}"
            )
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class JobApplicationResponse(BaseModel):
    """Job application representation returned by the API."""

    id: int
    user_id: int
    company_name: str
    role_title: str
    status: str
    job_url: str | None
    notes: str | None
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

"""Pydantic schemas for job description endpoints.

Covers request validation and response shapes for:
  POST   /api/v1/job-descriptions       → create
  GET    /api/v1/job-descriptions        → list
  GET    /api/v1/job-descriptions/{id}   → detail
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class JobDescriptionCreate(BaseModel):
    """Request body for creating a job description.

    title:            Job title, e.g. "Senior Python Developer".
    company:          Company name — optional, may be unknown.
    description_text: Full text of the job posting.  At least 20 characters
                      so there is enough content to extract skills from.
    """

    title: str = Field(min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    description_text: str = Field(min_length=20, max_length=50_000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class JobDescriptionResponse(BaseModel):
    """Safe job-description representation returned by the API.

    Never exposes the raw description_text in list responses to keep
    payloads lean — callers can fetch the detail endpoint for the full text.
    """

    id: int
    user_id: int
    title: str
    company: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobDescriptionDetailResponse(JobDescriptionResponse):
    """Full job-description including the raw description text.

    Returned by the detail endpoint (GET /{id}).
    """

    description_text: str

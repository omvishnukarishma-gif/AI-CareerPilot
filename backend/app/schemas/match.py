"""Pydantic schemas for job-match and skill-gap endpoints.

Covers:
  POST  /api/v1/matches               → create match + skill-gap
  GET   /api/v1/matches               → list user's matches
  GET   /api/v1/matches/{id}          → single match with skill-gap detail
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class MatchCreate(BaseModel):
    """Request body for running a resume–job match.

    resume_id:          ID of the resume to match (must belong to the caller).
    job_description_id: ID of the job description to match against
                        (must belong to the caller).
    """

    resume_id: int = Field(gt=0)
    job_description_id: int = Field(gt=0)


# ---------------------------------------------------------------------------
# Skill-gap sub-schema (embedded in match detail response)
# ---------------------------------------------------------------------------


class SkillGapResponse(BaseModel):
    """Detailed skill-gap analysis embedded in a match detail response.

    matched_skills:  Skills found in both resume and job description.
    missing_skills:  Skills required by the job but not found in the resume.
    recommendations: Actionable suggestions to close the gap.
    """

    id: int
    matched_skills: list[str]
    missing_skills: list[str]
    recommendations: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MatchResponse(BaseModel):
    """Match result returned by the list and create endpoints.

    Does not include the skill-gap detail — use GET /matches/{id} for that.
    """

    id: int
    resume_id: int
    job_description_id: int
    match_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}


class MatchDetailResponse(MatchResponse):
    """Full match result including skill-gap analysis.

    Returned by GET /matches/{id}.
    """

    skill_gap: SkillGapResponse | None = None

    # include the job description title for UI convenience
    job_description_title: str = ""
    resume_file_name: str = ""

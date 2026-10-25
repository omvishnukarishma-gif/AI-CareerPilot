"""Pydantic schemas for resume endpoints.

Three schemas cover the full surface:
- ResumeResponse       — upload (POST) and list (GET /) responses.
                         Excludes content_text and parsed_data.
- ResumeDetailResponse — single-resume detail (GET /{id}) response.
                         Includes content_text for the AI parsing phase.

The request for POST is multipart (UploadFile), not a JSON body, so no
request schema is needed here.
"""

from datetime import datetime

from pydantic import BaseModel, computed_field


class ResumeResponse(BaseModel):
    """Safe resume representation returned by the upload and list endpoints.

    Excludes content_text (bulk text) and parsed_data (AI output) to keep
    list responses lean.  file_type is derived from the stored filename.
    """

    id: int
    user_id: int
    file_name: str
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_type(self) -> str:
        """Return the extension (lowercase, without dot): 'pdf' or 'docx'."""
        return self.file_name.rsplit(".", 1)[-1].lower() if "." in self.file_name else ""

    model_config = {"from_attributes": True}


class ResumeDetailResponse(ResumeResponse):
    """Full resume representation returned by the detail endpoint (GET /{id}).

    Extends ResumeResponse with content_text so the AI parsing phase can
    read the extracted text without a separate database query.
    parsed_data is included so callers can check whether AI parsing has run.
    """

    content_text: str
    parsed_data: dict | None = None

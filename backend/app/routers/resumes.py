"""Resume router — file upload endpoint.

All endpoints are mounted under /api/v1/resumes (via main.py prefix).

Flow:
    POST /resumes → validate file, save to disk, persist metadata, return ResumeResponse

Security notes:
- The endpoint requires a valid Bearer token (get_current_user dependency).
- Uploaded filenames are sanitised and prefixed with a UUID so two users
  can upload files with the same name without collision, and path traversal
  characters are stripped.
- File contents are streamed in chunks; total size is tracked to enforce
  the configured limit without buffering the whole file in RAM.
- Magic bytes are checked so renaming a .exe to .pdf is still rejected.
- If the database commit fails after the file has been written to disk,
  the orphaned file is deleted before re-raising the exception.
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dependencies import get_current_user
from app.core.extractor import ExtractionError, extract_text
from app.core.llm import get_llm_provider
from app.database import get_db
from app.models import Resume, User
from app.schemas.resume import ResumeDetailResponse, ResumeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: set[str] = {"pdf", "docx"}
ALLOWED_CONTENT_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Some clients send this generic type for DOCX
    "application/octet-stream",
}

# Magic bytes: minimum header bytes that identify a file format.
# PDF files start with %PDF; DOCX (and all Office Open XML) files are ZIPs
# and start with PK\x03\x04.
_MAGIC: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _safe_extension(filename: str) -> str | None:
    """Return the lowercased extension if it is in ALLOWED_EXTENSIONS, else None."""
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else None


def _safe_filename(original: str, ext: str) -> str:
    """Build a collision-safe, path-traversal-free filename.

    Format: <uuid4_hex>_<sanitised_stem>.<ext>
    - Strip any directory component (basename only).
    - Replace characters outside [a-zA-Z0-9._-] with underscores.
    """
    basename = Path(original).name
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    safe_stem = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)
    safe_stem = safe_stem.strip("._") or "resume"
    return f"{uuid.uuid4().hex}_{safe_stem}.{ext}"


def _check_magic_bytes(data: bytes, ext: str) -> bool:
    """Return True if the file's leading bytes match the expected magic for ext."""
    magic = _MAGIC.get(ext)
    if magic is None:
        return True  # No magic defined → skip check
    return data[: len(magic)] == magic


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a resume",
    description=(
        "Upload a PDF or DOCX resume file. "
        "Returns the saved resume metadata. "
        "Requires a valid Bearer token."
    ),
)
def upload_resume(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    """Accept a PDF or DOCX upload, validate it, save it, and persist metadata.

    Validation order (each short-circuits with an appropriate HTTP error):
    1. Filename present and extension allowed (400 / 415).
    2. Content-type not explicitly wrong (415).
    3. Stream file: enforce non-empty (400) and size limit (413).
    4. Magic-byte check: file header matches declared extension (415).
    5. Text extraction: ExtractionError → 422, no file written, no DB record.
    6. Write to disk; on DB failure, delete the file and re-raise (500).
    """
    # --- 1. Extension ---
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    ext = _safe_extension(file.filename)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type. "
                f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    # --- 2. Content-type ---
    ct = (file.content_type or "").lower().split(";")[0].strip()
    if ct and ct not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type '{ct}'. Upload a PDF or DOCX file.",
        )

    # --- 3. Stream, check size ---
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = file.file.read(64 * 1024)  # 64 KB at a time
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File exceeds the maximum allowed size of "
                    f"{settings.max_upload_size_mb} MB."
                ),
            )
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    file_bytes = b"".join(chunks)

    # --- 4. Magic-byte validation ---
    if not _check_magic_bytes(file_bytes, ext):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File content does not match the declared type '{ext}'. "
                f"Ensure you are uploading a valid PDF or DOCX file."
            ),
        )

    # --- 5. Text extraction ---
    # Done before writing to disk so that a corrupt/encrypted/blank document
    # never produces an orphaned file or an empty database record.
    try:
        content_text = extract_text(file_bytes, ext)
    except ExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # --- 5b. Optional LLM analysis ---
    # Run before writing to disk. LLM failure must NEVER prevent the upload.
    parsed_data: dict | None = None
    provider = get_llm_provider()
    if provider is not None:
        try:
            result = provider.analyze_resume(content_text)
            if result is not None:
                parsed_data = result.model_dump()
        except Exception:  # noqa: BLE001
            logger.warning("LLM analyze_resume failed; continuing without parsed_data")

    # --- 6. Save to disk, then persist metadata ---
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    saved_filename = _safe_filename(file.filename, ext)
    dest = upload_path / saved_filename
    dest.write_bytes(file_bytes)

    # If the DB write fails, remove the orphaned file before propagating.
    try:
        resume = Resume(
            user_id=current_user.id,
            file_name=saved_filename,
            content_text=content_text,
            parsed_data=parsed_data,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
    except SQLAlchemyError:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save resume record. The uploaded file has been removed.",
        )

    return ResumeResponse.model_validate(resume)



@router.get(
    "",
    response_model=list[ResumeResponse],
    status_code=status.HTTP_200_OK,
    summary="List current user's resumes",
    description=(
        "Return all resumes belonging to the authenticated user, "
        "ordered by creation date (newest first). "
        "Returns an empty list if the user has no resumes. "
        "Requires a valid Bearer token."
    ),
)
def list_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResumeResponse]:
    """Return all resumes owned by the current user.

    Ownership is enforced by filtering on user_id — users never see
    each other's resumes.  content_text is intentionally omitted from
    ResumeResponse to keep the list payload lean.
    """
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc(), Resume.id.desc())
        .all()
    )
    return [ResumeResponse.model_validate(r) for r in resumes]


@router.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get one resume (with extracted text)",
    description=(
        "Return full details for a single resume, including content_text. "
        "Returns 404 if the resume does not exist or belongs to a different user. "
        "Requires a valid Bearer token."
    ),
)
def get_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeDetailResponse:
    """Return one resume owned by the current user, including content_text.

    Both non-existent IDs and IDs belonging to another user return 404.
    This prevents user enumeration — an attacker cannot determine whether
    a resume ID exists by probing the API with different tokens.
    """
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )
    return ResumeDetailResponse.model_validate(resume)


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a resume",
    description=(
        "Permanently delete a resume, including the uploaded file. "
        "Related job matches and skill gaps are automatically deleted. "
        "Interview sessions that reference this resume will have their "
        "resume_id set to NULL (the session is preserved). "
        "Returns 404 if the resume does not exist or belongs to a different user. "
        "Requires a valid Bearer token."
    ),
)
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete one resume owned by the current user.

    Deletes both the database record and the physical file from disk.
    Related records are handled via SQLAlchemy cascade (job_matches,
    skill_gaps) and database FK constraints (interview_sessions SET NULL).
    """
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )

    # Delete the physical file from disk
    upload_path = Path(settings.upload_dir)
    file_path = upload_path / resume.file_name
    if file_path.exists():
        file_path.unlink()

    # Delete the database record (cascades handled automatically)
    db.delete(resume)
    db.commit()

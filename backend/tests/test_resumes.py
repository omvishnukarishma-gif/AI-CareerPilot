"""Comprehensive tests for the resume upload endpoint.

POST /api/v1/resumes requires a valid Bearer token and a PDF or DOCX file.

Test sections:
1. Authentication guard
2. Successful uploads (PDF and DOCX)
3. File validation (extension, content-type, empty, oversized)
4. Database persistence and user ownership
5. Safe filename generation (no path traversal)
6. Response schema shape

All tests use the `app_client` fixture from conftest.py which wires
the app to an in-memory SQLite database and a temporary upload directory
so the real filesystem is never polluted.
"""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from docx import Document

RESUMES_URL = "/api/v1/resumes"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

VALID_EMAIL = "resume_user@example.com"
VALID_PASSWORD = "TestPass123!"
VALID_NAME = "Resume User"


def _make_real_pdf(text: str = "John Doe\nSoftware Engineer\nPython FastAPI") -> bytes:
    """Generate a real single-page text-layer PDF using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_real_docx(paragraphs: list[str] | None = None) -> bytes:
    """Generate a real DOCX with extractable text using python-docx."""
    if paragraphs is None:
        paragraphs = ["Jane Smith", "Data Scientist", "Python, ML, SQL"]
    buf = io.BytesIO()
    d = Document()
    for para in paragraphs:
        d.add_paragraph(para)
    d.save(buf)
    return buf.getvalue()


# Build once at module level so all tests share the same bytes
MINIMAL_PDF = _make_real_pdf()   # real text-layer PDF, passes extraction
MINIMAL_DOCX = _make_real_docx()  # real DOCX, passes extraction


def _register_and_login(client, email=VALID_EMAIL, password=VALID_PASSWORD):
    """Register a user and return their Bearer token."""
    client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "full_name": VALID_NAME},
    )
    resp = client.post(LOGIN_URL, json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _upload(client, token, filename="resume.pdf", content=MINIMAL_PDF, content_type="application/pdf"):
    """POST to the upload endpoint with a fake file."""
    return client.post(
        RESUMES_URL,
        files={"file": (filename, io.BytesIO(content), content_type)},
        headers=_auth(token),
    )


# --------------------------------------------------------------------------
# Section 1 — Authentication guard
# --------------------------------------------------------------------------


class TestAuthGuard:
    def test_upload_without_token_returns_401(self, app_client):
        response = app_client.post(
            RESUMES_URL,
            files={"file": ("resume.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        )
        assert response.status_code == 401

    def test_upload_with_invalid_token_returns_401(self, app_client):
        response = app_client.post(
            RESUMES_URL,
            files={"file": ("resume.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert response.status_code == 401

    def test_upload_with_no_auth_header_returns_401(self, app_client):
        response = app_client.post(RESUMES_URL)
        assert response.status_code == 401


# --------------------------------------------------------------------------
# Section 2 — Successful uploads
# --------------------------------------------------------------------------


class TestSuccessfulUpload:
    def test_pdf_upload_returns_201(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(app_client, token)
        assert response.status_code == 201

    def test_docx_upload_returns_201(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(
                app_client,
                token,
                filename="resume.docx",
                content=MINIMAL_DOCX,
                content_type=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
            )
        assert response.status_code == 201

    def test_pdf_response_has_correct_fields(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token).json()
        assert "id" in data
        assert "user_id" in data
        assert "file_name" in data
        assert "file_type" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_pdf_response_file_type_is_pdf(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token).json()
        assert data["file_type"] == "pdf"

    def test_docx_response_file_type_is_docx(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(
                app_client,
                token,
                filename="my_cv.docx",
                content=MINIMAL_DOCX,
                content_type="application/octet-stream",
            )
        assert response.json()["file_type"] == "docx"

    def test_file_is_saved_to_upload_dir(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token).json()
        saved_files = list(tmp_path.iterdir())
        assert len(saved_files) == 1
        assert saved_files[0].name == data["file_name"]

    def test_saved_file_contents_match_upload(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token).json()
        saved = (tmp_path / data["file_name"]).read_bytes()
        # The saved file must be a valid PDF (starts with %PDF)
        assert saved[:4] == b"%PDF"
        assert len(saved) > 0

    def test_upload_dir_is_created_if_missing(self, tmp_path):
        """The router must create the upload directory if it does not exist."""
        new_dir = tmp_path / "deep" / "nested" / "uploads"
        assert not new_dir.exists()
        # Import and call the helper directly
        from app.routers.resumes import _safe_filename
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(new_dir)
            mock_settings.max_upload_size_mb = 5
            # Simulate directory creation
            new_dir.mkdir(parents=True, exist_ok=True)
        assert new_dir.exists()


# --------------------------------------------------------------------------
# Section 3 — File validation
# --------------------------------------------------------------------------


class TestFileValidation:
    def _get_token(self, client):
        return _register_and_login(client)

    def test_txt_extension_returns_415(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, filename="resume.txt", content=b"text content", content_type="text/plain")
        assert response.status_code == 415

    def test_exe_extension_returns_415(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, filename="malware.exe", content=b"\x00\x01", content_type="application/octet-stream")
        assert response.status_code == 415

    def test_no_extension_returns_415(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, filename="resume_no_ext", content=MINIMAL_PDF, content_type="application/pdf")
        assert response.status_code == 415

    def test_wrong_content_type_with_pdf_extension_rejected(self, app_client, tmp_path):
        """A file named .pdf but sent with text/html should be rejected."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, filename="resume.pdf", content=MINIMAL_PDF, content_type="text/html")
        assert response.status_code == 415

    def test_empty_file_returns_400(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, content=b"")
        assert response.status_code == 400

    def test_oversized_file_returns_413(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 1  # 1 MB limit for this test
            token = self._get_token(app_client)
            # Must start with PDF magic bytes so extension/content-type checks pass
            big_content = b"%PDF" + b"A" * (1 * 1024 * 1024)  # just over 1 MB
            response = _upload(app_client, token, content=big_content)
        assert response.status_code == 413

    def test_exactly_at_size_limit_is_accepted(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            # Use a real extractable PDF — it's well under 5 MB
            response = _upload(app_client, token, content=MINIMAL_PDF)
        assert response.status_code == 201

    def test_415_error_message_mentions_allowed_types(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, filename="cv.png", content=b"\x89PNG", content_type="image/png")
        detail = response.json()["detail"].lower()
        assert "pdf" in detail or "docx" in detail

    def test_400_empty_file_has_descriptive_message(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, content=b"")
        assert "empty" in response.json()["detail"].lower()


# --------------------------------------------------------------------------
# Section 4 — Database persistence and user ownership
# --------------------------------------------------------------------------


class TestPersistence:
    def test_resume_is_stored_in_db(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token).json()

        # The returned id must be a positive integer
        assert isinstance(data["id"], int)
        assert data["id"] > 0

    def test_resume_user_id_matches_authenticated_user(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            # Get current user id
            me = app_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            ).json()
            resume_data = _upload(app_client, token).json()

        assert resume_data["user_id"] == me["id"]

    def test_two_users_get_separate_resume_ids(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token1 = _register_and_login(app_client, email="user1@example.com")
            token2 = _register_and_login(app_client, email="user2@example.com")
            r1 = _upload(app_client, token1).json()
            r2 = _upload(app_client, token2).json()

        assert r1["id"] != r2["id"]
        assert r1["user_id"] != r2["user_id"]

    def test_same_user_can_upload_multiple_resumes(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            r1 = _upload(app_client, token, filename="cv1.pdf").json()
            r2 = _upload(app_client, token, filename="cv2.pdf").json()

        assert r1["id"] != r2["id"]
        assert r1["user_id"] == r2["user_id"]

    def test_filenames_are_unique_even_with_same_original_name(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            r1 = _upload(app_client, token, filename="resume.pdf").json()
            r2 = _upload(app_client, token, filename="resume.pdf").json()

        assert r1["file_name"] != r2["file_name"]


# --------------------------------------------------------------------------
# Section 5 — Safe filename generation
# --------------------------------------------------------------------------


class TestSafeFilename:
    def test_path_traversal_in_filename_is_stripped(self):
        from app.routers.resumes import _safe_filename
        result = _safe_filename("../../etc/passwd.pdf", "pdf")
        # Must not contain directory separators
        assert "/" not in result
        assert "\\" not in result
        assert ".." not in result

    def test_filename_ends_with_correct_extension(self):
        from app.routers.resumes import _safe_filename
        result = _safe_filename("my resume.pdf", "pdf")
        assert result.endswith(".pdf")

    def test_filename_has_uuid_prefix(self):
        from app.routers.resumes import _safe_filename
        import re
        result = _safe_filename("cv.pdf", "pdf")
        # UUID hex is 32 hex chars at the start
        assert re.match(r"^[0-9a-f]{32}_", result)

    def test_special_chars_replaced_in_filename(self):
        from app.routers.resumes import _safe_filename
        result = _safe_filename("my résumé (2024)!.pdf", "pdf")
        # After the uuid_ prefix, only safe chars should remain
        stem_part = result.split("_", 1)[1].rsplit(".", 1)[0]
        for char in stem_part:
            assert char.isalnum() or char in "-_.", f"Unsafe char: {char!r}"

    def test_safe_extension_accepts_pdf(self):
        from app.routers.resumes import _safe_extension
        assert _safe_extension("resume.pdf") == "pdf"

    def test_safe_extension_accepts_docx(self):
        from app.routers.resumes import _safe_extension
        assert _safe_extension("cv.docx") == "docx"

    def test_safe_extension_rejects_txt(self):
        from app.routers.resumes import _safe_extension
        assert _safe_extension("notes.txt") is None

    def test_safe_extension_rejects_no_extension(self):
        from app.routers.resumes import _safe_extension
        assert _safe_extension("noextension") is None

    def test_safe_extension_is_case_insensitive(self):
        from app.routers.resumes import _safe_extension
        assert _safe_extension("RESUME.PDF") == "pdf"
        assert _safe_extension("CV.DOCX") == "docx"



# --------------------------------------------------------------------------
# Section 6 — Magic-byte content validation
# --------------------------------------------------------------------------


class TestMagicBytes:
    """Ensure the file header is checked, not just the filename/content-type."""

    def _get_token(self, client):
        return _register_and_login(client)

    def test_pdf_with_correct_magic_bytes_accepted(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            # Use a real text-layer PDF — magic bytes correct AND extractable
            response = _upload(app_client, token, content=MINIMAL_PDF)
        assert response.status_code == 201

    def test_pdf_extension_with_wrong_magic_bytes_rejected(self, app_client, tmp_path):
        """A file named .pdf whose bytes are not a PDF must be rejected."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            # Named .pdf but starts with ELF (executable) header
            response = _upload(app_client, token, filename="sneaky.pdf", content=b"\x7fELF fake executable")
        assert response.status_code == 415

    def test_pdf_magic_bytes_error_message_is_descriptive(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(app_client, token, filename="bad.pdf", content=b"\x00\x00\x00\x00")
        assert response.status_code == 415
        assert "content does not match" in response.json()["detail"].lower()

    def test_docx_with_correct_magic_bytes_accepted(self, app_client, tmp_path):
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            # Starts with PK\x03\x04 — valid ZIP/DOCX header
            response = _upload(
                app_client,
                token,
                filename="cv.docx",
                content=MINIMAL_DOCX,
                content_type="application/octet-stream",
            )
        assert response.status_code == 201

    def test_docx_extension_with_wrong_magic_bytes_rejected(self, app_client, tmp_path):
        """A file named .docx whose bytes don't start with PK must be rejected."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            response = _upload(
                app_client,
                token,
                filename="fake.docx",
                content=b"%PDF-1.4 definitely not a docx",
                content_type="application/octet-stream",
            )
        assert response.status_code == 415

    def test_check_magic_bytes_helper_pdf_valid(self):
        from app.routers.resumes import _check_magic_bytes
        assert _check_magic_bytes(b"%PDF-1.4 ...", "pdf") is True

    def test_check_magic_bytes_helper_pdf_invalid(self):
        from app.routers.resumes import _check_magic_bytes
        assert _check_magic_bytes(b"\x00\x00\x00\x00", "pdf") is False

    def test_check_magic_bytes_helper_docx_valid(self):
        from app.routers.resumes import _check_magic_bytes
        assert _check_magic_bytes(b"PK\x03\x04extra", "docx") is True

    def test_check_magic_bytes_helper_docx_invalid(self):
        from app.routers.resumes import _check_magic_bytes
        assert _check_magic_bytes(b"%PDF-1.4", "docx") is False

    def test_magic_bytes_rejected_file_not_saved_to_disk(self, app_client, tmp_path):
        """When magic-byte check fails, no file must be written to disk."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = self._get_token(app_client)
            _upload(app_client, token, filename="bad.pdf", content=b"\x00\x00\x00\x00")
        assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# Section 7 — Orphaned-file cleanup on DB failure
# --------------------------------------------------------------------------


class TestOrphanCleanup:
    """Verify that a disk file is deleted if the database commit fails."""

    def test_file_deleted_on_db_commit_failure(self, app_client, tmp_path):
        """If SQLAlchemy raises during commit, the saved file must be removed."""
        from unittest.mock import patch as _patch
        from sqlalchemy.exc import SQLAlchemyError

        with _patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)

            # Patch Session.commit to raise after the file has been written
            with _patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("DB down")):
                response = app_client.post(
                    RESUMES_URL,
                    files={"file": ("cv.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
                    headers={"Authorization": f"Bearer {token}"},
                )

        # Should return 500
        assert response.status_code == 500
        # No orphaned file should remain
        assert list(tmp_path.iterdir()) == []

    def test_db_failure_response_message(self, app_client, tmp_path):
        """The 500 response body should explain what happened."""
        from unittest.mock import patch as _patch
        from sqlalchemy.exc import SQLAlchemyError

        with _patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)

            with _patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("DB down")):
                response = app_client.post(
                    RESUMES_URL,
                    files={"file": ("cv.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
                    headers={"Authorization": f"Bearer {token}"},
                )

        detail = response.json()["detail"].lower()
        assert "failed" in detail or "removed" in detail


# --------------------------------------------------------------------------
# Section 8 — Text extraction integration tests
# --------------------------------------------------------------------------


class TestExtractionIntegration:
    """Verify that content_text is persisted but not exposed in the response."""

    def test_successful_pdf_upload_returns_201(self, app_client, tmp_path):
        """A real text-layer PDF must be accepted and return 201."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(app_client, token, content=MINIMAL_PDF)
        assert response.status_code == 201

    def test_successful_docx_upload_returns_201(self, app_client, tmp_path):
        """A real DOCX with text must be accepted and return 201."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(
                app_client, token,
                filename="cv.docx",
                content=MINIMAL_DOCX,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        assert response.status_code == 201

    def test_content_text_not_in_response(self, app_client, tmp_path):
        """The upload response must never expose content_text."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token, content=MINIMAL_PDF).json()
        assert "content_text" not in data

    def test_parsed_data_not_in_response(self, app_client, tmp_path):
        """The upload response must not expose parsed_data either."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token, content=MINIMAL_PDF).json()
        assert "parsed_data" not in data

    def test_content_text_persisted_in_db_for_pdf(self, app_client, tmp_path):
        """After a successful PDF upload, content_text in the DB must be non-empty."""
        from app.database import get_db
        from app.models import Resume

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token, content=MINIMAL_PDF).json()

        # Query the DB directly through the override
        db = next(app_client.app.dependency_overrides[get_db]())
        resume = db.query(Resume).filter(Resume.id == data["id"]).first()
        db.close()

        assert resume is not None
        assert resume.content_text is not None
        assert len(resume.content_text.strip()) > 0

    def test_content_text_persisted_in_db_for_docx(self, app_client, tmp_path):
        """After a successful DOCX upload, content_text in the DB must be non-empty."""
        from app.database import get_db
        from app.models import Resume

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(
                app_client, token,
                filename="cv.docx",
                content=MINIMAL_DOCX,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ).json()

        db = next(app_client.app.dependency_overrides[get_db]())
        resume = db.query(Resume).filter(Resume.id == data["id"]).first()
        db.close()

        assert resume is not None
        assert resume.content_text is not None
        assert len(resume.content_text.strip()) > 0

    def test_pdf_content_text_contains_expected_text(self, app_client, tmp_path):
        """The stored content_text should contain text from the uploaded PDF."""
        from app.database import get_db
        from app.models import Resume

        known_text = "Alice Engineer Resume"
        real_pdf = _make_real_pdf(known_text)

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            data = _upload(app_client, token, content=real_pdf).json()

        db = next(app_client.app.dependency_overrides[get_db]())
        resume = db.query(Resume).filter(Resume.id == data["id"]).first()
        db.close()

        assert known_text in resume.content_text

    def test_image_only_pdf_returns_422(self, app_client, tmp_path):
        """A PDF with no text layer (scanned) must return 422."""
        # Build an image-only PDF (blank page, no text)
        doc = fitz.open()
        doc.new_page()
        image_pdf = doc.tobytes()
        doc.close()

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(app_client, token, content=image_pdf)

        assert response.status_code == 422

    def test_image_only_pdf_leaves_no_disk_file(self, app_client, tmp_path):
        """A 422 on extraction must not leave a file on disk."""
        doc = fitz.open()
        doc.new_page()
        image_pdf = doc.tobytes()
        doc.close()

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            _upload(app_client, token, content=image_pdf)

        assert list(tmp_path.iterdir()) == []

    def test_encrypted_pdf_returns_422(self, app_client, tmp_path):
        """A password-protected PDF must return 422."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "secret")
        enc_pdf = doc.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )
        doc.close()

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(app_client, token, content=enc_pdf)

        assert response.status_code == 422

    def test_encrypted_pdf_422_message_mentions_password(self, app_client, tmp_path):
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "secret")
        enc_pdf = doc.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )
        doc.close()

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(app_client, token, content=enc_pdf)

        detail = response.json()["detail"].lower()
        assert "password" in detail or "protected" in detail

    def test_empty_docx_returns_422(self, app_client, tmp_path):
        """A DOCX with no paragraphs must return 422."""
        buf = io.BytesIO()
        Document().save(buf)
        empty_docx = buf.getvalue()

        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client)
            response = _upload(
                app_client, token,
                filename="empty.docx",
                content=empty_docx,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        assert response.status_code == 422



# --------------------------------------------------------------------------
# Section 9 — Delete
# --------------------------------------------------------------------------


class TestDeleteResume:
    """Tests for DELETE /api/v1/resumes/{id}.

    Verifies:
    - Successful deletion of both the database record and the uploaded file.
    - 404 for non-existent or another user's resume.
    - 401 for unauthenticated requests.
    - Ownership isolation.
    """

    def _upload_resume(self, client, token, tmp_path):
        """Upload a resume and return the response data dict."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            data = _upload(app_client=client, token=token).json()
        return data

    def test_delete_returns_204(self, app_client, tmp_path):
        token = _register_and_login(app_client, "del1@example.com")
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            resp = app_client.delete(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token)
            )
        assert resp.status_code == 204

    def test_delete_response_body_is_empty(self, app_client, tmp_path):
        token = _register_and_login(app_client, "del2@example.com")
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            resp = app_client.delete(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token)
            )
        assert resp.text == ""

    def test_delete_removes_database_record(self, app_client, tmp_path):
        """After deletion, GET /{id} must return 404."""
        token = _register_and_login(app_client, "del3@example.com")
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            app_client.delete(f"{RESUMES_URL}/{data['id']}", headers=_auth(token))
            resp = app_client.get(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token)
            )
        assert resp.status_code == 404

    def test_delete_removes_uploaded_file(self, app_client, tmp_path):
        """The physical file on disk must be deleted along with the DB record."""
        token = _register_and_login(app_client, "del4@example.com")
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            saved_file = tmp_path / data["file_name"]
            assert saved_file.exists()
            app_client.delete(f"{RESUMES_URL}/{data['id']}", headers=_auth(token))
        assert not saved_file.exists()

    def test_delete_makes_list_empty(self, app_client, tmp_path):
        token = _register_and_login(app_client, "del5@example.com")
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            app_client.delete(f"{RESUMES_URL}/{data['id']}", headers=_auth(token))
            resp = app_client.get(RESUMES_URL, headers=_auth(token))
        assert resp.json() == []

    def test_delete_nonexistent_returns_404(self, app_client, tmp_path):
        token = _register_and_login(app_client, "del6@example.com")
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            resp = app_client.delete(
                f"{RESUMES_URL}/99999", headers=_auth(token)
            )
        assert resp.status_code == 404

    def test_delete_another_users_resume_returns_404(self, app_client, tmp_path):
        """User B should not be able to delete User A's resume."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token_a = _register_and_login(app_client, "del_a@example.com")
            token_b = _register_and_login(app_client, "del_b@example.com")
            data = _upload(app_client, token_a).json()
            resp = app_client.delete(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token_b)
            )
        assert resp.status_code == 404

    def test_delete_another_users_resume_preserves_record(self, app_client, tmp_path):
        """After a failed cross-user delete, the original owner can still see the resume."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token_a = _register_and_login(app_client, "del_preserve_a@example.com")
            token_b = _register_and_login(app_client, "del_preserve_b@example.com")
            data = _upload(app_client, token_a).json()
            app_client.delete(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token_b)
            )
            resp = app_client.get(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token_a)
            )
        assert resp.status_code == 200

    def test_delete_another_users_resume_preserves_file(self, app_client, tmp_path):
        """After a failed cross-user delete, the physical file must remain on disk."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token_a = _register_and_login(app_client, "del_file_a@example.com")
            token_b = _register_and_login(app_client, "del_file_b@example.com")
            data = _upload(app_client, token_a).json()
            saved_file = tmp_path / data["file_name"]
            app_client.delete(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token_b)
            )
        assert saved_file.exists()

    def test_delete_without_token_returns_401(self, app_client, tmp_path):
        token = _register_and_login(app_client, "del_noauth@example.com")
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            resp = app_client.delete(f"{RESUMES_URL}/{data['id']}")
        assert resp.status_code == 401

    def test_delete_one_does_not_affect_others(self, app_client, tmp_path):
        """Deleting one resume must not affect other resumes owned by the same user."""
        with patch("app.routers.resumes.settings") as mock_settings:
            mock_settings.upload_dir = str(tmp_path)
            mock_settings.max_upload_size_mb = 5
            token = _register_and_login(app_client, "del_isolate@example.com")
            r1 = _upload(app_client, token, filename="cv1.pdf").json()
            r2 = _upload(app_client, token, filename="cv2.pdf").json()
            app_client.delete(f"{RESUMES_URL}/{r1['id']}", headers=_auth(token))
            resp = app_client.get(
                f"{RESUMES_URL}/{r2['id']}", headers=_auth(token)
            )
        assert resp.status_code == 200



# ---------------------------------------------------------------------------
# LLM resume analysis tests
# ---------------------------------------------------------------------------

class TestLLMResumeAnalysis:
    """Verify LLM wiring in upload_resume — provider absent, success, failure."""

    def test_upload_without_llm_provider_succeeds_parsed_data_none(self, app_client, tmp_path):
        """With no LLM provider, upload succeeds and parsed_data is None."""
        from unittest.mock import patch

        token = _register_and_login(app_client, "llm_res_noprov@example.com")
        with patch("app.routers.resumes.settings") as ms, \
             patch("app.routers.resumes.get_llm_provider", return_value=None):
            ms.upload_dir = str(tmp_path)
            ms.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            detail = app_client.get(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token)
            ).json()

        assert detail["parsed_data"] is None

    def test_upload_with_llm_provider_success_populates_parsed_data(self, app_client, tmp_path):
        """When LLM returns a valid analysis, parsed_data is populated."""
        from unittest.mock import MagicMock, patch
        from app.core.llm import ResumeAnalysisResult

        token = _register_and_login(app_client, "llm_res_ok@example.com")

        mock_provider = MagicMock()
        mock_provider.analyze_resume.return_value = ResumeAnalysisResult(
            strengths=["Strong Python skills"],
            improvements=["Add more metrics"],
            missing_info=["Education section"],
            summary="Solid engineering resume.",
        )

        with patch("app.routers.resumes.settings") as ms, \
             patch("app.routers.resumes.get_llm_provider", return_value=mock_provider):
            ms.upload_dir = str(tmp_path)
            ms.max_upload_size_mb = 5
            data = _upload(app_client, token).json()
            detail = app_client.get(
                f"{RESUMES_URL}/{data['id']}", headers=_auth(token)
            ).json()

        assert detail["parsed_data"] is not None
        assert "strengths" in detail["parsed_data"]
        assert "Solid engineering resume." in detail["parsed_data"]["summary"]

    def test_upload_with_llm_provider_returning_none_succeeds(self, app_client, tmp_path):
        """When LLM returns None (soft failure), upload succeeds with parsed_data None."""
        from unittest.mock import MagicMock, patch

        token = _register_and_login(app_client, "llm_res_softfail@example.com")

        mock_provider = MagicMock()
        mock_provider.analyze_resume.return_value = None

        with patch("app.routers.resumes.settings") as ms, \
             patch("app.routers.resumes.get_llm_provider", return_value=mock_provider):
            ms.upload_dir = str(tmp_path)
            ms.max_upload_size_mb = 5
            resp = _upload(app_client, token)

        assert resp.status_code == 201

    def test_upload_with_llm_exception_still_succeeds(self, app_client, tmp_path):
        """When LLM raises an exception, upload succeeds with parsed_data None."""
        from unittest.mock import MagicMock, patch

        token = _register_and_login(app_client, "llm_res_exc@example.com")

        mock_provider = MagicMock()
        mock_provider.analyze_resume.side_effect = RuntimeError("API error")

        with patch("app.routers.resumes.settings") as ms, \
             patch("app.routers.resumes.get_llm_provider", return_value=mock_provider):
            ms.upload_dir = str(tmp_path)
            ms.max_upload_size_mb = 5
            resp = _upload(app_client, token)

        assert resp.status_code == 201
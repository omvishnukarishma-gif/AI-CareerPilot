"""Tests for GET /api/v1/resumes and GET /api/v1/resumes/{id}.

These tests cover:
1. Authentication guard (both endpoints)
2. GET /resumes — empty list, single resume, multiple resumes, ordering,
   ownership isolation, response schema, content_text exclusion
3. GET /resumes/{id} — success, 404 for missing ID, 404 for cross-user,
   content_text present, parsed_data present, response schema
4. Content-text visibility rules (list excludes, detail includes)

All tests use the `app_client` fixture (in-memory SQLite, no PostgreSQL).
Resumes are created via the real upload endpoint using programmatically
generated PDF/DOCX bytes so the full validation + extraction stack runs.
"""

import io
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from docx import Document

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

LIST_URL = "/api/v1/resumes"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


def detail_url(resume_id: int) -> str:
    return f"/api/v1/resumes/{resume_id}"


# ---------------------------------------------------------------------------
# File-byte generators (real extractable documents)
# ---------------------------------------------------------------------------

def _make_pdf(text: str = "Alice Resume\nSoftware Engineer\nPython FastAPI") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_docx(paragraphs: list[str] | None = None) -> bytes:
    if paragraphs is None:
        paragraphs = ["Bob Resume", "Data Scientist", "Python ML SQL"]
    buf = io.BytesIO()
    d = Document()
    for p in paragraphs:
        d.add_paragraph(p)
    d.save(buf)
    return buf.getvalue()


# Build once per session
REAL_PDF = _make_pdf()
REAL_DOCX = _make_docx()

# ---------------------------------------------------------------------------
# Auth / upload helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, email: str, password: str = "TestPass1!") -> str:
    client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    resp = client.post(LOGIN_URL, json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _upload_pdf(client, token: str, tmp_path: Path, filename: str = "cv.pdf") -> dict:
    """Upload a real PDF and return the JSON response body."""
    with patch("app.routers.resumes.settings") as m:
        m.upload_dir = str(tmp_path)
        m.max_upload_size_mb = 5
        resp = client.post(
            LIST_URL,
            files={"file": (filename, io.BytesIO(REAL_PDF), "application/pdf")},
            headers=_auth(token),
        )
    assert resp.status_code == 201, f"Upload failed: {resp.json()}"
    return resp.json()


def _upload_docx(client, token: str, tmp_path: Path, filename: str = "cv.docx") -> dict:
    """Upload a real DOCX and return the JSON response body."""
    with patch("app.routers.resumes.settings") as m:
        m.upload_dir = str(tmp_path)
        m.max_upload_size_mb = 5
        resp = client.post(
            LIST_URL,
            files={
                "file": (
                    filename,
                    io.BytesIO(REAL_DOCX),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers=_auth(token),
        )
    assert resp.status_code == 201, f"Upload failed: {resp.json()}"
    return resp.json()


# ===========================================================================
# Section 1 — Authentication guard
# ===========================================================================


class TestListAuthGuard:
    def test_list_without_token_returns_401(self, app_client):
        assert app_client.get(LIST_URL).status_code == 401

    def test_list_with_invalid_token_returns_401(self, app_client):
        resp = app_client.get(LIST_URL, headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401


class TestDetailAuthGuard:
    def test_detail_without_token_returns_401(self, app_client):
        assert app_client.get(detail_url(1)).status_code == 401

    def test_detail_with_invalid_token_returns_401(self, app_client):
        resp = app_client.get(detail_url(1), headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401


# ===========================================================================
# Section 2 — GET /resumes (list)
# ===========================================================================


class TestListResumes:

    def test_empty_list_returns_200(self, app_client):
        token = _register_and_login(app_client, "empty@example.com")
        resp = app_client.get(LIST_URL, headers=_auth(token))
        assert resp.status_code == 200

    def test_empty_list_returns_empty_array(self, app_client):
        token = _register_and_login(app_client, "empty2@example.com")
        resp = app_client.get(LIST_URL, headers=_auth(token))
        assert resp.json() == []

    def test_single_upload_appears_in_list(self, app_client, tmp_path):
        token = _register_and_login(app_client, "single@example.com")
        _upload_pdf(app_client, token, tmp_path)
        resp = app_client.get(LIST_URL, headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_multiple_uploads_all_appear_in_list(self, app_client, tmp_path):
        token = _register_and_login(app_client, "multi@example.com")
        _upload_pdf(app_client, token, tmp_path, filename="cv1.pdf")
        _upload_pdf(app_client, token, tmp_path, filename="cv2.pdf")
        _upload_docx(app_client, token, tmp_path)
        resp = app_client.get(LIST_URL, headers=_auth(token))
        assert len(resp.json()) == 3

    def test_list_ordered_newest_first(self, app_client, tmp_path):
        """Resumes should be returned in descending created_at order."""
        token = _register_and_login(app_client, "order@example.com")
        r1 = _upload_pdf(app_client, token, tmp_path, filename="first.pdf")
        r2 = _upload_pdf(app_client, token, tmp_path, filename="second.pdf")
        items = app_client.get(LIST_URL, headers=_auth(token)).json()
        ids = [i["id"] for i in items]
        # r2 was created after r1, so it should appear first
        assert ids.index(r2["id"]) < ids.index(r1["id"])

    def test_list_response_contains_expected_fields(self, app_client, tmp_path):
        token = _register_and_login(app_client, "fields@example.com")
        _upload_pdf(app_client, token, tmp_path)
        item = app_client.get(LIST_URL, headers=_auth(token)).json()[0]
        assert "id" in item
        assert "user_id" in item
        assert "file_name" in item
        assert "file_type" in item
        assert "created_at" in item
        assert "updated_at" in item

    def test_list_does_not_include_content_text(self, app_client, tmp_path):
        token = _register_and_login(app_client, "notext@example.com")
        _upload_pdf(app_client, token, tmp_path)
        item = app_client.get(LIST_URL, headers=_auth(token)).json()[0]
        assert "content_text" not in item

    def test_list_does_not_include_parsed_data(self, app_client, tmp_path):
        token = _register_and_login(app_client, "noparsed@example.com")
        _upload_pdf(app_client, token, tmp_path)
        item = app_client.get(LIST_URL, headers=_auth(token)).json()[0]
        assert "parsed_data" not in item

    def test_list_file_type_derived_correctly_for_pdf(self, app_client, tmp_path):
        token = _register_and_login(app_client, "pdftype@example.com")
        _upload_pdf(app_client, token, tmp_path)
        item = app_client.get(LIST_URL, headers=_auth(token)).json()[0]
        assert item["file_type"] == "pdf"

    def test_list_file_type_derived_correctly_for_docx(self, app_client, tmp_path):
        token = _register_and_login(app_client, "docxtype@example.com")
        _upload_docx(app_client, token, tmp_path)
        item = app_client.get(LIST_URL, headers=_auth(token)).json()[0]
        assert item["file_type"] == "docx"

    def test_list_user_id_matches_authenticated_user(self, app_client, tmp_path):
        token = _register_and_login(app_client, "userid@example.com")
        me = app_client.get("/api/v1/auth/me", headers=_auth(token)).json()
        _upload_pdf(app_client, token, tmp_path)
        item = app_client.get(LIST_URL, headers=_auth(token)).json()[0]
        assert item["user_id"] == me["id"]

    def test_list_ownership_isolation(self, app_client, tmp_path):
        """User A's resumes must not appear in user B's list."""
        token_a = _register_and_login(app_client, "usera@example.com")
        token_b = _register_and_login(app_client, "userb@example.com")
        _upload_pdf(app_client, token_a, tmp_path, filename="a_cv.pdf")
        _upload_pdf(app_client, token_a, tmp_path, filename="a_cv2.pdf")
        _upload_pdf(app_client, token_b, tmp_path, filename="b_cv.pdf")

        list_a = app_client.get(LIST_URL, headers=_auth(token_a)).json()
        list_b = app_client.get(LIST_URL, headers=_auth(token_b)).json()

        assert len(list_a) == 2
        assert len(list_b) == 1

        ids_a = {r["id"] for r in list_a}
        ids_b = {r["id"] for r in list_b}
        assert ids_a.isdisjoint(ids_b)

    def test_list_returns_array_not_object(self, app_client):
        token = _register_and_login(app_client, "arraycheck@example.com")
        resp = app_client.get(LIST_URL, headers=_auth(token))
        assert isinstance(resp.json(), list)


# ===========================================================================
# Section 3 — GET /resumes/{id} (detail)
# ===========================================================================


class TestGetResumeDetail:

    def test_detail_returns_200_for_own_resume(self, app_client, tmp_path):
        token = _register_and_login(app_client, "detail200@example.com")
        uploaded = _upload_pdf(app_client, token, tmp_path)
        resp = app_client.get(detail_url(uploaded["id"]), headers=_auth(token))
        assert resp.status_code == 200

    def test_detail_response_has_correct_fields(self, app_client, tmp_path):
        token = _register_and_login(app_client, "detailfields@example.com")
        uploaded = _upload_pdf(app_client, token, tmp_path)
        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert "id" in data
        assert "user_id" in data
        assert "file_name" in data
        assert "file_type" in data
        assert "content_text" in data
        assert "parsed_data" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_detail_id_matches_requested(self, app_client, tmp_path):
        token = _register_and_login(app_client, "detailid@example.com")
        uploaded = _upload_pdf(app_client, token, tmp_path)
        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert data["id"] == uploaded["id"]

    def test_detail_content_text_is_non_empty_string(self, app_client, tmp_path):
        token = _register_and_login(app_client, "detailtext@example.com")
        uploaded = _upload_pdf(app_client, token, tmp_path)
        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert isinstance(data["content_text"], str)
        assert len(data["content_text"].strip()) > 0

    def test_detail_content_text_contains_pdf_text(self, app_client, tmp_path):
        """The content_text returned must contain the text embedded in the PDF."""
        known_text = "CareerPilot Detail Test Resume"
        real_pdf = _make_pdf(known_text)
        token = _register_and_login(app_client, "detailpdftext@example.com")

        with patch("app.routers.resumes.settings") as m:
            m.upload_dir = str(tmp_path)
            m.max_upload_size_mb = 5
            uploaded = app_client.post(
                LIST_URL,
                files={"file": ("cv.pdf", io.BytesIO(real_pdf), "application/pdf")},
                headers=_auth(token),
            ).json()

        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert known_text in data["content_text"]

    def test_detail_content_text_contains_docx_text(self, app_client, tmp_path):
        known_para = "CareerPilot DOCX Detail Test"
        real_docx = _make_docx([known_para, "Senior Engineer"])
        token = _register_and_login(app_client, "detaildocxtext@example.com")

        with patch("app.routers.resumes.settings") as m:
            m.upload_dir = str(tmp_path)
            m.max_upload_size_mb = 5
            uploaded = app_client.post(
                LIST_URL,
                files={
                    "file": (
                        "cv.docx",
                        io.BytesIO(real_docx),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                headers=_auth(token),
            ).json()

        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert known_para in data["content_text"]

    def test_detail_parsed_data_is_none_before_ai_parsing(self, app_client, tmp_path):
        """parsed_data must be null until the AI parsing phase populates it."""
        token = _register_and_login(app_client, "nullparsed@example.com")
        uploaded = _upload_pdf(app_client, token, tmp_path)
        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert data["parsed_data"] is None

    def test_detail_user_id_matches_token(self, app_client, tmp_path):
        token = _register_and_login(app_client, "detailuserid@example.com")
        me = app_client.get("/api/v1/auth/me", headers=_auth(token)).json()
        uploaded = _upload_pdf(app_client, token, tmp_path)
        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert data["user_id"] == me["id"]

    def test_detail_nonexistent_id_returns_404(self, app_client):
        token = _register_and_login(app_client, "notfound@example.com")
        resp = app_client.get(detail_url(99999), headers=_auth(token))
        assert resp.status_code == 404

    def test_detail_404_has_descriptive_message(self, app_client):
        token = _register_and_login(app_client, "notfoundmsg@example.com")
        resp = app_client.get(detail_url(99999), headers=_auth(token))
        assert "not found" in resp.json()["detail"].lower()

    def test_detail_cross_user_access_returns_404(self, app_client, tmp_path):
        """User B must not be able to retrieve user A's resume — returns 404."""
        token_a = _register_and_login(app_client, "ownerA@example.com")
        token_b = _register_and_login(app_client, "ownerB@example.com")
        uploaded_a = _upload_pdf(app_client, token_a, tmp_path)

        resp = app_client.get(detail_url(uploaded_a["id"]), headers=_auth(token_b))
        assert resp.status_code == 404

    def test_detail_cross_user_returns_404_not_403(self, app_client, tmp_path):
        """Ownership violations must return 404, not 403, to prevent enumeration."""
        token_a = _register_and_login(app_client, "enumA@example.com")
        token_b = _register_and_login(app_client, "enumB@example.com")
        uploaded_a = _upload_pdf(app_client, token_a, tmp_path)

        resp = app_client.get(detail_url(uploaded_a["id"]), headers=_auth(token_b))
        assert resp.status_code == 404
        assert resp.status_code != 403

    def test_detail_integer_zero_id_returns_404(self, app_client):
        token = _register_and_login(app_client, "zeroid@example.com")
        resp = app_client.get(detail_url(0), headers=_auth(token))
        assert resp.status_code == 404

    def test_detail_file_type_derived_correctly(self, app_client, tmp_path):
        token = _register_and_login(app_client, "detailft@example.com")
        uploaded = _upload_docx(app_client, token, tmp_path)
        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert data["file_type"] == "docx"


# ===========================================================================
# Section 4 — content_text visibility rules
# ===========================================================================


class TestContentTextVisibility:
    """Explicit tests for the content_text exposure contract."""

    def test_upload_response_does_not_expose_content_text(self, app_client, tmp_path):
        token = _register_and_login(app_client, "vis_upload@example.com")
        with patch("app.routers.resumes.settings") as m:
            m.upload_dir = str(tmp_path)
            m.max_upload_size_mb = 5
            resp = app_client.post(
                LIST_URL,
                files={"file": ("cv.pdf", io.BytesIO(REAL_PDF), "application/pdf")},
                headers=_auth(token),
            )
        assert "content_text" not in resp.json()

    def test_list_response_does_not_expose_content_text(self, app_client, tmp_path):
        token = _register_and_login(app_client, "vis_list@example.com")
        _upload_pdf(app_client, token, tmp_path)
        items = app_client.get(LIST_URL, headers=_auth(token)).json()
        for item in items:
            assert "content_text" not in item

    def test_detail_response_exposes_content_text(self, app_client, tmp_path):
        token = _register_and_login(app_client, "vis_detail@example.com")
        uploaded = _upload_pdf(app_client, token, tmp_path)
        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        assert "content_text" in data
        assert isinstance(data["content_text"], str)

    def test_detail_content_text_is_same_as_what_was_extracted(self, app_client, tmp_path):
        """Round-trip: upload PDF, get detail, content_text matches extraction."""
        from app.core.extractor import extract_text

        known_text = "RoundTrip Extraction Verify"
        real_pdf = _make_pdf(known_text)
        token = _register_and_login(app_client, "roundtrip@example.com")

        with patch("app.routers.resumes.settings") as m:
            m.upload_dir = str(tmp_path)
            m.max_upload_size_mb = 5
            uploaded = app_client.post(
                LIST_URL,
                files={"file": ("cv.pdf", io.BytesIO(real_pdf), "application/pdf")},
                headers=_auth(token),
            ).json()

        data = app_client.get(detail_url(uploaded["id"]), headers=_auth(token)).json()
        expected = extract_text(real_pdf, "pdf")
        assert data["content_text"] == expected

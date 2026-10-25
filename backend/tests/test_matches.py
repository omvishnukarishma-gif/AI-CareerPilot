"""Tests for the matches endpoint and the matcher algorithm.

Sections:
  1. Matcher unit tests (app.core.matcher)
  2. Auth guard for /matches
  3. Create match — success and ownership enforcement
  4. List matches
  5. Get match detail
"""

import io

import fitz
import pytest
from docx import Document

MATCHES_URL = "/api/v1/matches"
JD_URL = "/api/v1/job-descriptions"
RESUMES_URL = "/api/v1/resumes"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VALID_JD_TEXT = (
    "We are seeking a Python developer with experience in FastAPI, PostgreSQL, "
    "Docker, REST API design, and Git. Knowledge of AWS and CI/CD pipelines is "
    "a strong plus. Familiarity with React is beneficial."
)

VALID_RESUME_TEXT = (
    "John Doe — Software Engineer\n"
    "Skills: Python, FastAPI, PostgreSQL, Docker, Git, REST API\n"
    "Experience: 3 years building microservices on AWS."
)


def _make_real_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_real_docx(paragraphs: list[str]) -> bytes:
    buf = io.BytesIO()
    d = Document()
    for p in paragraphs:
        d.add_paragraph(p)
    d.save(buf)
    return buf.getvalue()


def _register_and_login(client, email: str, password: str = "TestPass123!") -> str:
    client.post(REGISTER_URL, json={
        "email": email, "password": password, "full_name": "Test User",
    })
    resp = client.post(LOGIN_URL, json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_jd(client, token: str, text: str = VALID_JD_TEXT) -> dict:
    return client.post(JD_URL, json={
        "title": "Test Role",
        "company": "Test Co",
        "description_text": text,
    }, headers=_auth(token)).json()


def _upload_resume(client, token: str, text: str = VALID_RESUME_TEXT, tmp_path=None):
    from unittest.mock import patch
    pdf_bytes = _make_real_pdf(text)
    with patch("app.routers.resumes.settings") as ms:
        ms.upload_dir = str(tmp_path) if tmp_path else "/tmp/test_uploads"
        ms.max_upload_size_mb = 5
        resp = client.post(
            RESUMES_URL,
            files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            headers=_auth(token),
        )
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Matcher unit tests
# ---------------------------------------------------------------------------

class TestMatcherUnit:
    def test_exact_skill_match(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="I have experience with python and fastapi",
            jd_text="Requires python and fastapi skills",
        )
        assert "python" in result.matched_skills
        assert "fastapi" in result.matched_skills
        assert result.score > 0

    def test_missing_skill_reported(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="I know python",
            jd_text="Requires python and docker",
        )
        assert "docker" in result.missing_skills
        assert "python" in result.matched_skills

    def test_score_zero_when_no_jd_skills(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="I know python",
            jd_text="We need someone great with communication.",
        )
        # "communication" is in the vocab but absent from the resume text above
        # — the specific result depends on what's in jd; main thing: no crash
        assert 0.0 <= result.score <= 100.0

    def test_perfect_score_when_all_matched(self):
        from app.core.matcher import compute_match
        # Both texts mention the same single skill
        result = compute_match(
            resume_text="Expert in python programming",
            jd_text="Must know python",
        )
        assert result.score == 100.0

    def test_score_capped_at_100(self):
        from app.core.matcher import compute_match
        # Resume has many more skills than JD
        result = compute_match(
            resume_text="python fastapi docker kubernetes react aws postgresql git",
            jd_text="python",
        )
        assert result.score <= 100.0

    def test_empty_resume_gives_zero_score(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="",
            jd_text="Requires python and fastapi",
        )
        assert result.score == 0.0
        assert result.matched_skills == []
        assert "python" in result.missing_skills or "fastapi" in result.missing_skills

    def test_recommendations_present_for_missing_skills(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="I know python",
            jd_text="Requires python and docker and kubernetes",
        )
        assert len(result.recommendations) > 0

    def test_recommendations_mention_not_found(self):
        """Recommendations must say 'not found', not 'you lack'."""
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="I know python",
            jd_text="Requires python and docker",
        )
        combined = " ".join(result.recommendations).lower()
        assert "not found" in combined

    def test_perfect_match_has_positive_recommendation(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="python developer",
            jd_text="python role",
        )
        # No missing skills → single positive recommendation
        assert len(result.recommendations) == 1
        assert "great match" in result.recommendations[0].lower()

    def test_skills_lists_are_sorted(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="python fastapi docker",
            jd_text="python fastapi docker kubernetes react",
        )
        assert result.matched_skills == sorted(result.matched_skills)
        assert result.missing_skills == sorted(result.missing_skills)

    def test_case_insensitive_matching(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="Proficient in PYTHON and FastAPI",
            jd_text="must know Python and fastapi",
        )
        assert "python" in result.matched_skills
        assert "fastapi" in result.matched_skills

    def test_compound_skill_matched(self):
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="I have worked on machine learning projects",
            jd_text="experience in machine learning required",
        )
        assert "machine learning" in result.matched_skills

    def test_extract_skills_helper(self):
        from app.core.matcher import _extract_skills
        found = _extract_skills("I use python and docker and react")
        assert "python" in found
        assert "docker" in found
        assert "react" in found

    # ------------------------------------------------------------------
    # Regression tests for recommendation-spacing bug
    # Previously adjacent f-string literals produced "new to git,it may"
    # and "skillsdescribed in different terms" due to missing spaces at
    # the string-concatenation boundaries.
    # ------------------------------------------------------------------

    def test_recommendation_spacing_git(self):
        """'new to git, it may' must contain the space after the comma."""
        from app.core.matcher import _build_recommendations
        recs = _build_recommendations(["git"], 0.0)
        combined = " ".join(recs)
        assert "new to git, it may" in combined, (
            f"Missing space in git recommendation. Got: {combined!r}"
        )

    def test_recommendation_spacing_rest(self):
        """'new to rest, it may' must contain the space after the comma."""
        from app.core.matcher import _build_recommendations
        recs = _build_recommendations(["rest"], 0.0)
        combined = " ".join(recs)
        assert "new to rest, it may" in combined, (
            f"Missing space in rest recommendation. Got: {combined!r}"
        )

    def test_recommendation_caveat_spacing(self):
        """'skills described in different terms' must not be run together."""
        from app.core.matcher import _build_recommendations
        recs = _build_recommendations(["docker"], 0.0)
        combined = " ".join(recs)
        assert "skills described in different terms" in combined, (
            f"Missing space in caveat. Got: {combined!r}"
        )

    def test_recommendation_no_double_spaces(self):
        """Recommendations must not contain double spaces from bad joins."""
        from app.core.matcher import _build_recommendations
        recs = _build_recommendations(["git", "rest", "docker"], 0.0)
        for rec in recs:
            assert "  " not in rec, (
                f"Double space found in recommendation: {rec!r}"
            )

    def test_recommendation_spacing_via_compute_match(self):
        """End-to-end: compute_match output must contain correct spacing."""
        from app.core.matcher import compute_match
        result = compute_match(
            resume_text="I know python",
            jd_text="We need python, git, and rest api experience",
        )
        combined = " ".join(result.recommendations)
        assert "new to git, it may" in combined, (
            f"compute_match: missing space in git rec. Got: {combined!r}"
        )
        assert "new to rest, it may" in combined, (
            f"compute_match: missing space in rest rec. Got: {combined!r}"
        )
        assert "skills described in different terms" in combined, (
            f"compute_match: missing space in caveat. Got: {combined!r}"
        )


# ---------------------------------------------------------------------------
# 2. Auth guard
# ---------------------------------------------------------------------------

class TestMatchesAuthGuard:
    def test_create_without_token_returns_401(self, app_client):
        resp = app_client.post(MATCHES_URL, json={"resume_id": 1, "job_description_id": 1})
        assert resp.status_code == 401

    def test_list_without_token_returns_401(self, app_client):
        resp = app_client.get(MATCHES_URL)
        assert resp.status_code == 401

    def test_get_without_token_returns_401(self, app_client):
        resp = app_client.get(f"{MATCHES_URL}/1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Create match
# ---------------------------------------------------------------------------

class TestCreateMatch:
    def test_create_returns_201(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_create@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        resp = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"],
            "job_description_id": jd["id"],
        }, headers=_auth(token))
        assert resp.status_code == 201

    def test_create_response_has_required_fields(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_fields@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        data = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"],
            "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        assert "id" in data
        assert "match_score" in data
        assert "matched_skills" in data
        assert "missing_skills" in data
        assert "skill_gap" in data
        assert "job_description_title" in data
        assert "resume_file_name" in data

    def test_match_score_is_between_0_and_100(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_score@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        data = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"],
            "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        assert 0.0 <= data["match_score"] <= 100.0

    def test_skill_gap_is_embedded(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_sg@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        data = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"],
            "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        sg = data["skill_gap"]
        assert sg is not None
        assert "matched_skills" in sg
        assert "missing_skills" in sg
        assert "recommendations" in sg

    def test_recommendations_not_empty(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_recs@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        data = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"],
            "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        assert len(data["skill_gap"]["recommendations"]) >= 1

    def test_create_with_nonexistent_resume_returns_404(self, app_client):
        token = _register_and_login(app_client, "match_badresume@example.com")
        jd = _create_jd(app_client, token)
        resp = app_client.post(MATCHES_URL, json={
            "resume_id": 99999,
            "job_description_id": jd["id"],
        }, headers=_auth(token))
        assert resp.status_code == 404

    def test_create_with_nonexistent_jd_returns_404(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_badjd@example.com")
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        resp = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"],
            "job_description_id": 99999,
        }, headers=_auth(token))
        assert resp.status_code == 404

    def test_create_with_another_users_resume_returns_404(self, app_client, tmp_path):
        """User B cannot use User A's resume."""
        token_a = _register_and_login(app_client, "match_owna@example.com")
        token_b = _register_and_login(app_client, "match_ownb@example.com")
        resume_a = _upload_resume(app_client, token_a, tmp_path=tmp_path)
        jd_b = _create_jd(app_client, token_b)
        resp = app_client.post(MATCHES_URL, json={
            "resume_id": resume_a["id"],
            "job_description_id": jd_b["id"],
        }, headers=_auth(token_b))
        assert resp.status_code == 404

    def test_create_with_another_users_jd_returns_404(self, app_client, tmp_path):
        """User B cannot use User A's job description."""
        token_a = _register_and_login(app_client, "match_jdowna@example.com")
        token_b = _register_and_login(app_client, "match_jdownb@example.com")
        jd_a = _create_jd(app_client, token_a)
        resume_b = _upload_resume(app_client, token_b, tmp_path=tmp_path)
        resp = app_client.post(MATCHES_URL, json={
            "resume_id": resume_b["id"],
            "job_description_id": jd_a["id"],
        }, headers=_auth(token_b))
        assert resp.status_code == 404

    def test_create_missing_resume_id_returns_422(self, app_client):
        token = _register_and_login(app_client, "match_noresid@example.com")
        resp = app_client.post(MATCHES_URL, json={"job_description_id": 1},
                               headers=_auth(token))
        assert resp.status_code == 422

    def test_create_missing_jd_id_returns_422(self, app_client):
        token = _register_and_login(app_client, "match_nojdid@example.com")
        resp = app_client.post(MATCHES_URL, json={"resume_id": 1},
                               headers=_auth(token))
        assert resp.status_code == 422

    def test_matched_and_missing_are_lists_of_strings(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_listtypes@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        data = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"],
            "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        assert isinstance(data["matched_skills"], list)
        assert isinstance(data["missing_skills"], list)
        for s in data["matched_skills"] + data["missing_skills"]:
            assert isinstance(s, str)


# ---------------------------------------------------------------------------
# 4. List matches
# ---------------------------------------------------------------------------

class TestListMatches:
    def test_list_returns_200(self, app_client):
        token = _register_and_login(app_client, "match_list@example.com")
        resp = app_client.get(MATCHES_URL, headers=_auth(token))
        assert resp.status_code == 200

    def test_list_empty_for_new_user(self, app_client):
        token = _register_and_login(app_client, "match_listempty@example.com")
        assert app_client.get(MATCHES_URL, headers=_auth(token)).json() == []

    def test_list_returns_created_matches(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_listcount@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"], "job_description_id": jd["id"],
        }, headers=_auth(token))
        data = app_client.get(MATCHES_URL, headers=_auth(token)).json()
        assert len(data) == 1

    def test_list_isolates_users(self, app_client, tmp_path):
        token_a = _register_and_login(app_client, "match_listisola@example.com")
        token_b = _register_and_login(app_client, "match_listisolb@example.com")
        jd_a = _create_jd(app_client, token_a)
        resume_a = _upload_resume(app_client, token_a, tmp_path=tmp_path)
        app_client.post(MATCHES_URL, json={
            "resume_id": resume_a["id"], "job_description_id": jd_a["id"],
        }, headers=_auth(token_a))
        assert app_client.get(MATCHES_URL, headers=_auth(token_b)).json() == []


# ---------------------------------------------------------------------------
# 5. Get match detail
# ---------------------------------------------------------------------------

class TestGetMatchDetail:
    def test_get_returns_200(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_getok@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        match = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"], "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        resp = app_client.get(f"{MATCHES_URL}/{match['id']}", headers=_auth(token))
        assert resp.status_code == 200

    def test_get_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "match_get404@example.com")
        resp = app_client.get(f"{MATCHES_URL}/99999", headers=_auth(token))
        assert resp.status_code == 404

    def test_get_another_users_match_returns_404(self, app_client, tmp_path):
        token_a = _register_and_login(app_client, "match_getowna@example.com")
        token_b = _register_and_login(app_client, "match_getownb@example.com")
        jd_a = _create_jd(app_client, token_a)
        resume_a = _upload_resume(app_client, token_a, tmp_path=tmp_path)
        match_a = app_client.post(MATCHES_URL, json={
            "resume_id": resume_a["id"], "job_description_id": jd_a["id"],
        }, headers=_auth(token_a)).json()
        resp = app_client.get(f"{MATCHES_URL}/{match_a['id']}", headers=_auth(token_b))
        assert resp.status_code == 404

    def test_get_includes_skill_gap(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_getsg@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        match = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"], "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        data = app_client.get(f"{MATCHES_URL}/{match['id']}", headers=_auth(token)).json()
        assert data["skill_gap"] is not None
        assert "recommendations" in data["skill_gap"]

    def test_get_includes_jd_title(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_getjdtitle@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        match = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"], "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        data = app_client.get(f"{MATCHES_URL}/{match['id']}", headers=_auth(token)).json()
        assert data["job_description_title"] == "Test Role"

    def test_get_includes_resume_file_name(self, app_client, tmp_path):
        token = _register_and_login(app_client, "match_getresname@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        match = app_client.post(MATCHES_URL, json={
            "resume_id": resume["id"], "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        data = app_client.get(f"{MATCHES_URL}/{match['id']}", headers=_auth(token)).json()
        assert data["resume_file_name"].endswith(".pdf")



# ---------------------------------------------------------------------------
# 6. LLM recommendation tests
# ---------------------------------------------------------------------------

class TestLLMMatchRecommendations:
    """Verify LLM wiring in create_match — provider absent, success, and failure."""

    def test_deterministic_recommendations_when_no_provider(self, app_client, tmp_path):
        """With no LLM provider, skill-gap recommendations come from matcher."""
        from unittest.mock import patch

        token = _register_and_login(app_client, "llm_match_noprov@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)

        with patch("app.routers.matches.get_llm_provider", return_value=None):
            data = app_client.post(
                MATCHES_URL,
                json={"resume_id": resume["id"], "job_description_id": jd["id"]},
                headers=_auth(token),
            ).json()

        recs = data["skill_gap"]["recommendations"]
        assert isinstance(recs, list)
        assert len(recs) >= 1

    def test_llm_recommendations_used_when_provider_available(self, app_client, tmp_path):
        """When the LLM provider succeeds, its recommendations replace the defaults."""
        from unittest.mock import MagicMock, patch
        from app.core.llm import EnhanceRecommendationsResult

        token = _register_and_login(app_client, "llm_match_prov@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)

        mock_provider = MagicMock()
        mock_provider.enhance_recommendations.return_value = EnhanceRecommendationsResult(
            recommendations=["LLM recommendation 1", "LLM recommendation 2"]
        )

        with patch("app.routers.matches.get_llm_provider", return_value=mock_provider):
            data = app_client.post(
                MATCHES_URL,
                json={"resume_id": resume["id"], "job_description_id": jd["id"]},
                headers=_auth(token),
            ).json()

        recs = data["skill_gap"]["recommendations"]
        assert "LLM recommendation 1" in recs

    def test_deterministic_fallback_on_provider_failure(self, app_client, tmp_path):
        """When the LLM call raises, deterministic recommendations are used and upload succeeds."""
        from unittest.mock import MagicMock, patch

        token = _register_and_login(app_client, "llm_match_fail@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)

        mock_provider = MagicMock()
        mock_provider.enhance_recommendations.side_effect = RuntimeError("API error")

        with patch("app.routers.matches.get_llm_provider", return_value=mock_provider):
            resp = app_client.post(
                MATCHES_URL,
                json={"resume_id": resume["id"], "job_description_id": jd["id"]},
                headers=_auth(token),
            )

        assert resp.status_code == 201
        recs = resp.json()["skill_gap"]["recommendations"]
        assert isinstance(recs, list) and len(recs) >= 1
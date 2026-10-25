"""Tests for the interview-sessions endpoints and the interviewer engine.

Sections:
  1.  Interviewer unit tests (app.core.interviewer)
  2.  Auth guard for /interview-sessions
  3.  Create session — success and validation
  4.  Create session — optional resume / JD ownership
  5.  List sessions — ordering and isolation
  6.  Get session detail — success and ownership
  7.  Submit answer — normal flow
  8.  Submit answer — edge cases and error paths
  9.  Session completion (all questions answered)
  10. Persistence — data survives commit
"""

import io

import fitz
import pytest
from docx import Document

SESSION_URL = "/api/v1/interview-sessions"
JD_URL = "/api/v1/job-descriptions"
RESUMES_URL = "/api/v1/resumes"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

VALID_JD_TEXT = (
    "We are seeking a Python developer with experience in FastAPI, PostgreSQL, "
    "Docker, REST API design, and Git. Knowledge of AWS and CI/CD pipelines is "
    "a strong plus. Familiarity with React is beneficial."
)

VALID_RESUME_TEXT = (
    "Jane Smith — Software Engineer\n"
    "Skills: Python, FastAPI, PostgreSQL, Git\n"
    "Experience: 2 years building REST API services."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_docx(paragraphs: list[str]) -> bytes:
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
        "title": "Python Developer",
        "company": "Test Co",
        "description_text": text,
    }, headers=_auth(token)).json()


def _upload_resume(client, token: str, text: str = VALID_RESUME_TEXT, tmp_path=None) -> dict:
    from unittest.mock import patch
    pdf_bytes = _make_pdf(text)
    with patch("app.routers.resumes.settings") as ms:
        ms.upload_dir = str(tmp_path) if tmp_path else "/tmp/test_uploads"
        ms.max_upload_size_mb = 5
        resp = client.post(
            RESUMES_URL,
            files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            headers=_auth(token),
        )
    return resp.json()


def _create_session(
    client,
    token: str,
    role_target: str = "Backend Engineer",
    jd_id: int | None = None,
    resume_id: int | None = None,
) -> dict:
    payload: dict = {"role_target": role_target}
    if jd_id is not None:
        payload["job_description_id"] = jd_id
    if resume_id is not None:
        payload["resume_id"] = resume_id
    return client.post(SESSION_URL, json=payload, headers=_auth(token)).json()


# ---------------------------------------------------------------------------
# 1. Interviewer unit tests
# ---------------------------------------------------------------------------


class TestInterviewerUnit:
    def test_generate_questions_returns_list(self):
        from app.core.interviewer import generate_questions
        qs = generate_questions("Backend Engineer")
        assert isinstance(qs, list)
        assert len(qs) > 0

    def test_generate_questions_categories_present(self):
        from app.core.interviewer import generate_questions
        qs = generate_questions("Python Developer")
        categories = {q.category for q in qs}
        assert "behavioral" in categories
        assert "technical" in categories

    def test_generate_questions_with_jd_adds_jd_skill_questions(self):
        from app.core.interviewer import generate_questions
        qs = generate_questions("Backend Engineer", jd_text=VALID_JD_TEXT)
        categories = {q.category for q in qs}
        assert "jd_skill" in categories

    def test_generate_questions_role_specific_python(self):
        from app.core.interviewer import generate_questions
        qs = generate_questions("Senior Python Developer")
        role_qs = [q for q in qs if q.category == "role_specific"]
        assert len(role_qs) > 0

    def test_generate_questions_deterministic(self):
        from app.core.interviewer import generate_questions
        qs1 = generate_questions("Backend Engineer", jd_text=VALID_JD_TEXT)
        qs2 = generate_questions("Backend Engineer", jd_text=VALID_JD_TEXT)
        assert [q.text for q in qs1] == [q.text for q in qs2]

    def test_generate_questions_missing_skills_prioritised(self):
        """Questions about missing skills should appear when both JD and resume supplied."""
        from app.core.interviewer import generate_questions
        qs = generate_questions(
            "Python Developer",
            jd_text="Requires python, docker, kubernetes, aws",
            resume_text="Python developer",  # only python → docker/k8s/aws missing
        )
        jd_skill_refs = [q.skill_ref for q in qs if q.category == "jd_skill"]
        # Missing skills (docker, kubernetes, aws) should be in skill refs
        assert any(ref in ("docker", "kubernetes", "aws") for ref in jd_skill_refs if ref)

    def test_question_to_dict_and_back(self):
        from app.core.interviewer import Question
        q = Question(
            text="Test question?",
            category="technical",
            expected_keywords=["foo", "bar"],
            skill_ref="python",
        )
        assert Question.from_dict(q.to_dict()) == q

    def test_evaluate_answer_returns_result(self):
        from app.core.interviewer import Question, evaluate_answer
        q = Question(text="Tell me about Python.", category="technical",
                     expected_keywords=["python", "language"])
        result = evaluate_answer(q, "Python is a high-level programming language.")
        assert 0.0 <= result.score <= 100.0
        assert isinstance(result.strengths, list)
        assert isinstance(result.improvements, list)
        assert isinstance(result.note, str)

    def test_evaluate_answer_short_answer_flagged(self):
        from app.core.interviewer import Question, evaluate_answer
        q = Question(text="Tell me about Python.", category="technical",
                     expected_keywords=["python"])
        result = evaluate_answer(q, "Python is good.")
        assert any("expand" in s.lower() or "word" in s.lower() for s in result.improvements)

    def test_evaluate_answer_empty_answer_low_score(self):
        from app.core.interviewer import Question, evaluate_answer
        q = Question(text="Describe REST.", category="technical",
                     expected_keywords=["rest", "http", "stateless"])
        result = evaluate_answer(q, "   ")
        # Empty/whitespace-only answers should score very low
        assert result.score < 30

    def test_evaluate_answer_keyword_match_increases_score(self):
        from app.core.interviewer import Question, evaluate_answer
        q = Question(text="Explain REST.", category="technical",
                     expected_keywords=["rest", "http", "stateless", "resource"])
        poor = evaluate_answer(q, "I don't know much about it honestly.")
        good = evaluate_answer(q, "REST is stateless, uses http methods, and treats everything as a resource.")
        assert good.score > poor.score

    def test_evaluate_behavioral_star_markers_detected(self):
        from app.core.interviewer import Question, evaluate_answer
        q = Question(text="Tell me about a challenge.", category="behavioral",
                     expected_keywords=["challenge", "resolved"])
        answer = (
            "Situation: our service was down. Task: restore it quickly. "
            "Action: I diagnosed the issue. Result: restored in 20 minutes."
        )
        result = evaluate_answer(q, answer)
        assert any("star" in s.lower() or "structure" in s.lower() for s in result.strengths)

    def test_evaluation_result_to_dict(self):
        from app.core.interviewer import EvaluationResult
        er = EvaluationResult(score=75.0, strengths=["Good"], improvements=["More detail"], note="heuristic")
        d = er.to_dict()
        assert d["score"] == 75.0
        assert "strengths" in d
        assert "improvements" in d
        assert "note" in d

    def test_note_mentions_keyword_matching(self):
        from app.core.interviewer import Question, evaluate_answer
        q = Question(text="Describe Python.", category="technical", expected_keywords=["python"])
        result = evaluate_answer(q, "Python is a programming language I use daily.")
        assert "keyword" in result.note.lower()


# ---------------------------------------------------------------------------
# 2. Auth guard
# ---------------------------------------------------------------------------


class TestAuthGuard:
    def test_create_without_token_returns_401(self, app_client):
        resp = app_client.post(SESSION_URL, json={"role_target": "Engineer"})
        assert resp.status_code == 401

    def test_list_without_token_returns_401(self, app_client):
        resp = app_client.get(SESSION_URL)
        assert resp.status_code == 401

    def test_get_without_token_returns_401(self, app_client):
        resp = app_client.get(f"{SESSION_URL}/1")
        assert resp.status_code == 401

    def test_submit_without_token_returns_401(self, app_client):
        resp = app_client.post(f"{SESSION_URL}/1/answers",
                                json={"question_index": 0, "answer": "Some answer."})
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, app_client):
        resp = app_client.post(SESSION_URL, json={"role_target": "Engineer"},
                               headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Create session — success and validation
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_create_returns_201(self, app_client):
        token = _register_and_login(app_client, "sess_create@example.com")
        resp = app_client.post(SESSION_URL, json={"role_target": "Backend Engineer"},
                               headers=_auth(token))
        assert resp.status_code == 201

    def test_create_response_has_expected_fields(self, app_client):
        token = _register_and_login(app_client, "sess_fields@example.com")
        data = app_client.post(SESSION_URL, json={"role_target": "Backend Engineer"},
                               headers=_auth(token)).json()
        assert "id" in data
        assert "user_id" in data
        assert data["role_target"] == "Backend Engineer"
        assert data["status"] == "started"
        assert isinstance(data["questions"], list)
        assert isinstance(data["transcript"], list)
        assert data["transcript"] == []
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_generates_questions(self, app_client):
        token = _register_and_login(app_client, "sess_qs@example.com")
        data = app_client.post(SESSION_URL, json={"role_target": "Backend Engineer"},
                               headers=_auth(token)).json()
        assert len(data["questions"]) >= 3

    def test_create_questions_have_text_and_category(self, app_client):
        token = _register_and_login(app_client, "sess_qshape@example.com")
        data = app_client.post(SESSION_URL, json={"role_target": "Backend Engineer"},
                               headers=_auth(token)).json()
        for q in data["questions"]:
            assert "text" in q
            assert "category" in q
            assert q["text"] != ""

    def test_create_questions_do_not_include_expected_keywords(self, app_client):
        """expected_keywords is internal; it must not be sent to the client."""
        token = _register_and_login(app_client, "sess_nokw@example.com")
        data = app_client.post(SESSION_URL, json={"role_target": "Backend Engineer"},
                               headers=_auth(token)).json()
        for q in data["questions"]:
            assert "expected_keywords" not in q

    def test_create_missing_role_target_returns_422(self, app_client):
        token = _register_and_login(app_client, "sess_norole@example.com")
        resp = app_client.post(SESSION_URL, json={}, headers=_auth(token))
        assert resp.status_code == 422

    def test_create_empty_role_target_returns_422(self, app_client):
        token = _register_and_login(app_client, "sess_emptyrole@example.com")
        resp = app_client.post(SESSION_URL, json={"role_target": ""},
                               headers=_auth(token))
        assert resp.status_code == 422

    def test_create_short_role_target_returns_422(self, app_client):
        token = _register_and_login(app_client, "sess_shortrole@example.com")
        resp = app_client.post(SESSION_URL, json={"role_target": "X"},
                               headers=_auth(token))
        assert resp.status_code == 422

    def test_create_sets_correct_user_id(self, app_client):
        token = _register_and_login(app_client, "sess_uid@example.com")
        me = app_client.get("/api/v1/auth/me", headers=_auth(token)).json()
        data = app_client.post(SESSION_URL, json={"role_target": "Engineer"},
                               headers=_auth(token)).json()
        assert data["user_id"] == me["id"]

    def test_create_with_jd_adds_jd_skill_questions(self, app_client):
        token = _register_and_login(app_client, "sess_wjd@example.com")
        jd = _create_jd(app_client, token)
        data = app_client.post(SESSION_URL, json={
            "role_target": "Backend Engineer",
            "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        categories = [q["category"] for q in data["questions"]]
        assert "jd_skill" in categories

    def test_create_stores_jd_id(self, app_client):
        token = _register_and_login(app_client, "sess_storjd@example.com")
        jd = _create_jd(app_client, token)
        data = app_client.post(SESSION_URL, json={
            "role_target": "Backend Engineer",
            "job_description_id": jd["id"],
        }, headers=_auth(token)).json()
        assert data["job_description_id"] == jd["id"]

    def test_create_without_optional_ids_stores_nulls(self, app_client):
        token = _register_and_login(app_client, "sess_nullids@example.com")
        data = app_client.post(SESSION_URL, json={"role_target": "Engineer"},
                               headers=_auth(token)).json()
        assert data["job_description_id"] is None
        assert data["resume_id"] is None


# ---------------------------------------------------------------------------
# 4. Create session — optional resume / JD ownership
# ---------------------------------------------------------------------------


class TestSessionOwnershipOnCreate:
    def test_nonexistent_jd_returns_404(self, app_client):
        token = _register_and_login(app_client, "sess_nojd@example.com")
        resp = app_client.post(SESSION_URL, json={
            "role_target": "Engineer",
            "job_description_id": 99999,
        }, headers=_auth(token))
        assert resp.status_code == 404

    def test_another_users_jd_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "sess_owna_jd@example.com")
        token_b = _register_and_login(app_client, "sess_ownb_jd@example.com")
        jd_a = _create_jd(app_client, token_a)
        resp = app_client.post(SESSION_URL, json={
            "role_target": "Engineer",
            "job_description_id": jd_a["id"],
        }, headers=_auth(token_b))
        assert resp.status_code == 404

    def test_nonexistent_resume_returns_404(self, app_client):
        token = _register_and_login(app_client, "sess_nores@example.com")
        resp = app_client.post(SESSION_URL, json={
            "role_target": "Engineer",
            "resume_id": 99999,
        }, headers=_auth(token))
        assert resp.status_code == 404

    def test_another_users_resume_returns_404(self, app_client, tmp_path):
        token_a = _register_and_login(app_client, "sess_owna_res@example.com")
        token_b = _register_and_login(app_client, "sess_ownb_res@example.com")
        resume_a = _upload_resume(app_client, token_a, tmp_path=tmp_path)
        resp = app_client.post(SESSION_URL, json={
            "role_target": "Engineer",
            "resume_id": resume_a["id"],
        }, headers=_auth(token_b))
        assert resp.status_code == 404

    def test_create_with_own_resume_and_jd_succeeds(self, app_client, tmp_path):
        token = _register_and_login(app_client, "sess_fullown@example.com")
        jd = _create_jd(app_client, token)
        resume = _upload_resume(app_client, token, tmp_path=tmp_path)
        resp = app_client.post(SESSION_URL, json={
            "role_target": "Backend Engineer",
            "job_description_id": jd["id"],
            "resume_id": resume["id"],
        }, headers=_auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["resume_id"] == resume["id"]
        assert data["job_description_id"] == jd["id"]


# ---------------------------------------------------------------------------
# 5. List sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    def test_list_returns_200(self, app_client):
        token = _register_and_login(app_client, "sess_list@example.com")
        resp = app_client.get(SESSION_URL, headers=_auth(token))
        assert resp.status_code == 200

    def test_list_empty_for_new_user(self, app_client):
        token = _register_and_login(app_client, "sess_listempty@example.com")
        assert app_client.get(SESSION_URL, headers=_auth(token)).json() == []

    def test_list_returns_created_sessions(self, app_client):
        token = _register_and_login(app_client, "sess_listcount@example.com")
        app_client.post(SESSION_URL, json={"role_target": "Engineer"}, headers=_auth(token))
        app_client.post(SESSION_URL, json={"role_target": "Developer"}, headers=_auth(token))
        data = app_client.get(SESSION_URL, headers=_auth(token)).json()
        assert len(data) == 2

    def test_list_response_shape(self, app_client):
        token = _register_and_login(app_client, "sess_listshape@example.com")
        app_client.post(SESSION_URL, json={"role_target": "Engineer"}, headers=_auth(token))
        data = app_client.get(SESSION_URL, headers=_auth(token)).json()
        item = data[0]
        assert "id" in item
        assert "role_target" in item
        assert "status" in item
        assert "question_count" in item
        assert "answers_given" in item
        # Full questions list and transcript should NOT be in list response
        assert "questions" not in item
        assert "transcript" not in item

    def test_list_isolates_users(self, app_client):
        token_a = _register_and_login(app_client, "sess_listisolb@example.com")
        token_b = _register_and_login(app_client, "sess_listisola@example.com")
        app_client.post(SESSION_URL, json={"role_target": "Engineer"}, headers=_auth(token_a))
        assert app_client.get(SESSION_URL, headers=_auth(token_b)).json() == []

    def test_list_ordered_newest_first(self, app_client):
        token = _register_and_login(app_client, "sess_listorder@example.com")
        app_client.post(SESSION_URL, json={"role_target": "First"}, headers=_auth(token))
        app_client.post(SESSION_URL, json={"role_target": "Second"}, headers=_auth(token))
        data = app_client.get(SESSION_URL, headers=_auth(token)).json()
        assert data[0]["role_target"] == "Second"
        assert data[1]["role_target"] == "First"

    def test_list_question_count_correct(self, app_client):
        token = _register_and_login(app_client, "sess_qcount@example.com")
        created = app_client.post(SESSION_URL, json={"role_target": "Engineer"},
                                  headers=_auth(token)).json()
        listed = app_client.get(SESSION_URL, headers=_auth(token)).json()
        assert listed[0]["question_count"] == len(created["questions"])


# ---------------------------------------------------------------------------
# 6. Get session detail
# ---------------------------------------------------------------------------


class TestGetSessionDetail:
    def test_get_returns_200(self, app_client):
        token = _register_and_login(app_client, "sess_getok@example.com")
        session = _create_session(app_client, token)
        resp = app_client.get(f"{SESSION_URL}/{session['id']}", headers=_auth(token))
        assert resp.status_code == 200

    def test_get_includes_questions(self, app_client):
        token = _register_and_login(app_client, "sess_getqs@example.com")
        session = _create_session(app_client, token)
        data = app_client.get(f"{SESSION_URL}/{session['id']}", headers=_auth(token)).json()
        assert len(data["questions"]) > 0

    def test_get_includes_empty_transcript(self, app_client):
        token = _register_and_login(app_client, "sess_gettrans@example.com")
        session = _create_session(app_client, token)
        data = app_client.get(f"{SESSION_URL}/{session['id']}", headers=_auth(token)).json()
        assert data["transcript"] == []

    def test_get_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "sess_get404@example.com")
        resp = app_client.get(f"{SESSION_URL}/99999", headers=_auth(token))
        assert resp.status_code == 404

    def test_get_another_users_session_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "sess_getowna@example.com")
        token_b = _register_and_login(app_client, "sess_getownb@example.com")
        session_a = _create_session(app_client, token_a)
        resp = app_client.get(f"{SESSION_URL}/{session_a['id']}", headers=_auth(token_b))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. Submit answer — normal flow
# ---------------------------------------------------------------------------


class TestSubmitAnswer:
    def test_submit_returns_200(self, app_client):
        token = _register_and_login(app_client, "ans_submit@example.com")
        session = _create_session(app_client, token)
        answer_text = "I approached the problem by first understanding the requirements."
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": answer_text},
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_submit_appends_to_transcript(self, app_client):
        token = _register_and_login(app_client, "ans_transcript@example.com")
        session = _create_session(app_client, token)
        answer_text = "I approached this by breaking down the problem into steps and collaborating with my team."
        data = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": answer_text},
            headers=_auth(token),
        ).json()
        assert len(data["transcript"]) == 1
        entry = data["transcript"][0]
        assert entry["question_index"] == 0
        assert entry["answer"] == answer_text
        assert "feedback" in entry

    def test_submit_feedback_has_score(self, app_client):
        token = _register_and_login(app_client, "ans_score@example.com")
        session = _create_session(app_client, token)
        data = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "I worked through the challenge step by step."},
            headers=_auth(token),
        ).json()
        feedback = data["transcript"][0]["feedback"]
        assert 0.0 <= feedback["score"] <= 100.0

    def test_submit_feedback_has_strengths_and_improvements(self, app_client):
        token = _register_and_login(app_client, "ans_feedback@example.com")
        session = _create_session(app_client, token)
        data = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "I worked through the challenge step by step."},
            headers=_auth(token),
        ).json()
        feedback = data["transcript"][0]["feedback"]
        assert isinstance(feedback["strengths"], list)
        assert isinstance(feedback["improvements"], list)
        assert len(feedback["strengths"]) >= 1
        assert len(feedback["improvements"]) >= 1

    def test_submit_feedback_has_note(self, app_client):
        token = _register_and_login(app_client, "ans_note@example.com")
        session = _create_session(app_client, token)
        data = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "My answer to the question is detailed."},
            headers=_auth(token),
        ).json()
        note = data["transcript"][0]["feedback"]["note"]
        assert isinstance(note, str)
        assert len(note) > 10

    def test_submit_stores_question_text_snapshot(self, app_client):
        token = _register_and_login(app_client, "ans_qsnapshot@example.com")
        session = _create_session(app_client, token)
        q_text = session["questions"][0]["text"]
        data = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "I resolved it by careful analysis."},
            headers=_auth(token),
        ).json()
        assert data["transcript"][0]["question_text"] == q_text

    def test_submit_session_remains_started_with_more_questions(self, app_client):
        token = _register_and_login(app_client, "ans_stillstarted@example.com")
        session = _create_session(app_client, token)
        # If there are more than 1 questions, status stays started after the first answer
        if len(session["questions"]) > 1:
            data = app_client.post(
                f"{SESSION_URL}/{session['id']}/answers",
                json={"question_index": 0, "answer": "I worked through this carefully."},
                headers=_auth(token),
            ).json()
            assert data["status"] == "started"


# ---------------------------------------------------------------------------
# 8. Submit answer — error paths
# ---------------------------------------------------------------------------


class TestSubmitAnswerErrors:
    def test_submit_to_nonexistent_session_returns_404(self, app_client):
        token = _register_and_login(app_client, "ans_404sess@example.com")
        resp = app_client.post(
            f"{SESSION_URL}/99999/answers",
            json={"question_index": 0, "answer": "Some answer here."},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_submit_to_another_users_session_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "ans_own404a@example.com")
        token_b = _register_and_login(app_client, "ans_own404b@example.com")
        session_a = _create_session(app_client, token_a)
        resp = app_client.post(
            f"{SESSION_URL}/{session_a['id']}/answers",
            json={"question_index": 0, "answer": "My answer to the question."},
            headers=_auth(token_b),
        )
        assert resp.status_code == 404

    def test_submit_out_of_range_index_returns_422(self, app_client):
        token = _register_and_login(app_client, "ans_oob@example.com")
        session = _create_session(app_client, token)
        out_of_range = len(session["questions"]) + 10
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": out_of_range, "answer": "Some answer here."},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_submit_duplicate_answer_returns_409(self, app_client):
        token = _register_and_login(app_client, "ans_dup@example.com")
        session = _create_session(app_client, token)
        app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "First answer to this question."},
            headers=_auth(token),
        )
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "Second attempt at same question."},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_submit_empty_answer_returns_422(self, app_client):
        token = _register_and_login(app_client, "ans_empty@example.com")
        session = _create_session(app_client, token)
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": ""},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_submit_too_short_answer_returns_422(self, app_client):
        token = _register_and_login(app_client, "ans_short@example.com")
        session = _create_session(app_client, token)
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "Hi"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_submit_missing_answer_field_returns_422(self, app_client):
        token = _register_and_login(app_client, "ans_missingfield@example.com")
        session = _create_session(app_client, token)
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_submit_negative_index_returns_422(self, app_client):
        token = _register_and_login(app_client, "ans_negidx@example.com")
        session = _create_session(app_client, token)
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": -1, "answer": "Some answer here."},
            headers=_auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 9. Session completion
# ---------------------------------------------------------------------------


class TestSessionCompletion:
    def _answer_all(self, client, token: str, session: dict) -> dict:
        """Submit acceptable answers for every question and return final state."""
        current = session
        for i, _ in enumerate(session["questions"]):
            current = client.post(
                f"{SESSION_URL}/{session['id']}/answers",
                json={
                    "question_index": i,
                    "answer": (
                        "I worked on this situation carefully. "
                        "The task required me to take specific action. "
                        "The result was a successful outcome delivered on time."
                    ),
                },
                headers=_auth(token),
            ).json()
        return current

    def test_session_completed_after_all_answers(self, app_client):
        token = _register_and_login(app_client, "sess_complete@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        final = self._answer_all(app_client, token, session)
        assert final["status"] == "completed"

    def test_all_questions_answered_in_transcript(self, app_client):
        token = _register_and_login(app_client, "sess_alltrans@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        final = self._answer_all(app_client, token, session)
        assert len(final["transcript"]) == len(session["questions"])

    def test_submit_to_completed_session_returns_409(self, app_client):
        token = _register_and_login(app_client, "sess_completed409@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        self._answer_all(app_client, token, session)
        # Now try to answer any question again
        resp = app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": "Trying again after completion."},
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_completed_session_visible_in_list(self, app_client):
        token = _register_and_login(app_client, "sess_completelist@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        self._answer_all(app_client, token, session)
        listed = app_client.get(SESSION_URL, headers=_auth(token)).json()
        assert listed[0]["status"] == "completed"
        assert listed[0]["answers_given"] == listed[0]["question_count"]


# ---------------------------------------------------------------------------
# 10. Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_session_persisted_and_retrievable(self, app_client):
        token = _register_and_login(app_client, "sess_persist@example.com")
        created = _create_session(app_client, token, role_target="Backend Engineer")
        fetched = app_client.get(f"{SESSION_URL}/{created['id']}",
                                 headers=_auth(token)).json()
        assert fetched["id"] == created["id"]
        assert fetched["role_target"] == "Backend Engineer"
        assert len(fetched["questions"]) == len(created["questions"])

    def test_answer_persisted_after_submit(self, app_client):
        token = _register_and_login(app_client, "sess_persisnans@example.com")
        session = _create_session(app_client, token)
        answer_text = "I carefully analysed the situation and delivered a good solution."
        app_client.post(
            f"{SESSION_URL}/{session['id']}/answers",
            json={"question_index": 0, "answer": answer_text},
            headers=_auth(token),
        )
        # Fetch fresh from DB
        fetched = app_client.get(f"{SESSION_URL}/{session['id']}",
                                 headers=_auth(token)).json()
        assert len(fetched["transcript"]) == 1
        assert fetched["transcript"][0]["answer"] == answer_text
        assert fetched["transcript"][0]["feedback"]["score"] >= 0

    def test_multiple_answers_all_persisted(self, app_client):
        token = _register_and_login(app_client, "sess_multians@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        n = min(2, len(session["questions"]))
        for i in range(n):
            app_client.post(
                f"{SESSION_URL}/{session['id']}/answers",
                json={"question_index": i,
                      "answer": "Detailed answer covering situation task action result."},
                headers=_auth(token),
            )
        fetched = app_client.get(f"{SESSION_URL}/{session['id']}",
                                 headers=_auth(token)).json()
        assert len(fetched["transcript"]) == n



# ---------------------------------------------------------------------------
# LLM feedback tests
# ---------------------------------------------------------------------------

class TestLLMInterviewFeedback:
    """Verify LLM wiring in submit_answer — provider absent, success, failure."""

    def test_deterministic_feedback_when_no_provider(self, app_client):
        """With no LLM provider, feedback fields come from the deterministic evaluator."""
        from unittest.mock import patch

        token = _register_and_login(app_client, "llm_feed_noprov@example.com")
        session = _create_session(app_client, token, role_target="Engineer")

        with patch("app.routers.interview_sessions.get_llm_provider", return_value=None):
            resp = app_client.post(
                f"{SESSION_URL}/{session['id']}/answers",
                json={"question_index": 0, "answer": "I solved it by analysing the problem carefully."},
                headers=_auth(token),
            )

        assert resp.status_code == 200
        entry = resp.json()["transcript"][0]
        fb = entry["feedback"]
        assert "score" in fb and "strengths" in fb and "improvements" in fb and "note" in fb

    def test_llm_feedback_used_when_provider_available(self, app_client):
        """When LLM provider succeeds, its feedback replaces deterministic output."""
        from unittest.mock import MagicMock, patch
        from app.core.llm import EnhanceFeedbackResult

        token = _register_and_login(app_client, "llm_feed_prov@example.com")
        session = _create_session(app_client, token, role_target="Engineer")

        mock_provider = MagicMock()
        mock_provider.enhance_feedback.return_value = EnhanceFeedbackResult(
            score=88.0,
            strengths=["Clear explanation"],
            improvements=["Add more detail"],
            note="Good answer",
        )

        with patch("app.routers.interview_sessions.get_llm_provider", return_value=mock_provider):
            resp = app_client.post(
                f"{SESSION_URL}/{session['id']}/answers",
                json={"question_index": 0, "answer": "I solved it by analysing the problem."},
                headers=_auth(token),
            )

        assert resp.status_code == 200
        fb = resp.json()["transcript"][0]["feedback"]
        assert fb["score"] == 88.0
        assert "Clear explanation" in fb["strengths"]

    def test_deterministic_fallback_on_llm_failure(self, app_client):
        """When LLM raises, deterministic feedback is used and the request succeeds."""
        from unittest.mock import MagicMock, patch

        token = _register_and_login(app_client, "llm_feed_fail@example.com")
        session = _create_session(app_client, token, role_target="Engineer")

        mock_provider = MagicMock()
        mock_provider.enhance_feedback.side_effect = RuntimeError("LLM down")

        with patch("app.routers.interview_sessions.get_llm_provider", return_value=mock_provider):
            resp = app_client.post(
                f"{SESSION_URL}/{session['id']}/answers",
                json={"question_index": 0, "answer": "I handled it step by step."},
                headers=_auth(token),
            )

        assert resp.status_code == 200
        fb = resp.json()["transcript"][0]["feedback"]
        assert "score" in fb


# ---------------------------------------------------------------------------
# DELETE interview session tests
# ---------------------------------------------------------------------------

class TestDeleteInterviewSession:
    """Verify DELETE /interview-sessions/{id} behavior."""

    def test_delete_own_session_returns_204(self, app_client):
        token = _register_and_login(app_client, "del_sess_ok@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        resp = app_client.delete(f"{SESSION_URL}/{session['id']}", headers=_auth(token))
        assert resp.status_code == 204

    def test_deleted_session_no_longer_in_list(self, app_client):
        token = _register_and_login(app_client, "del_sess_list@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        app_client.delete(f"{SESSION_URL}/{session['id']}", headers=_auth(token))
        ids = [s["id"] for s in app_client.get(SESSION_URL, headers=_auth(token)).json()]
        assert session["id"] not in ids

    def test_delete_nonexistent_session_returns_404(self, app_client):
        token = _register_and_login(app_client, "del_sess_404@example.com")
        resp = app_client.delete(f"{SESSION_URL}/99999", headers=_auth(token))
        assert resp.status_code == 404

    def test_delete_another_users_session_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "del_sess_owna@example.com")
        token_b = _register_and_login(app_client, "del_sess_ownb@example.com")
        session_a = _create_session(app_client, token_a, role_target="Engineer")
        resp = app_client.delete(f"{SESSION_URL}/{session_a['id']}", headers=_auth(token_b))
        assert resp.status_code == 404

    def test_delete_without_token_returns_401(self, app_client):
        token = _register_and_login(app_client, "del_sess_noauth@example.com")
        session = _create_session(app_client, token, role_target="Engineer")
        resp = app_client.delete(f"{SESSION_URL}/{session['id']}")
        assert resp.status_code == 401
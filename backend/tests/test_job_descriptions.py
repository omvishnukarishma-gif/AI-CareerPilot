"""Tests for the job descriptions endpoints.

Covers:
  POST   /api/v1/job-descriptions      — create
  GET    /api/v1/job-descriptions       — list
  GET    /api/v1/job-descriptions/{id}  — detail
  PUT    /api/v1/job-descriptions/{id}  — update (full replacement)
  DELETE /api/v1/job-descriptions/{id}  — delete

Sections:
  1. Auth guard
  2. Create — success and validation
  3. List — ownership isolation
  4. Get detail — success and 404
  5. Update — success, validation, 404, ownership
  6. Delete — success, 404, ownership
"""

import pytest

JD_URL = "/api/v1/job-descriptions"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

VALID_JD = {
    "title": "Senior Python Developer",
    "company": "Acme Corp",
    "description_text": (
        "We are looking for a Python developer with experience in FastAPI, "
        "PostgreSQL, Docker, and REST API design. Knowledge of AWS and CI/CD "
        "pipelines is a plus."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, email: str, password: str = "TestPass123!") -> str:
    client.post(REGISTER_URL, json={
        "email": email, "password": password, "full_name": "Test User"
    })
    resp = client.post(LOGIN_URL, json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_create_without_token_returns_401(self, app_client):
        resp = app_client.post(JD_URL, json=VALID_JD)
        assert resp.status_code == 401

    def test_list_without_token_returns_401(self, app_client):
        resp = app_client.get(JD_URL)
        assert resp.status_code == 401

    def test_get_without_token_returns_401(self, app_client):
        resp = app_client.get(f"{JD_URL}/1")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, app_client):
        resp = app_client.post(JD_URL, json=VALID_JD,
                               headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401

    def test_update_without_token_returns_401(self, app_client):
        resp = app_client.put(f"{JD_URL}/1", json=VALID_JD)
        assert resp.status_code == 401

    def test_delete_without_token_returns_401(self, app_client):
        resp = app_client.delete(f"{JD_URL}/1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Create
# ---------------------------------------------------------------------------

class TestCreateJobDescription:
    def test_create_returns_201(self, app_client):
        token = _register_and_login(app_client, "jd_create@example.com")
        resp = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token))
        assert resp.status_code == 201

    def test_create_response_has_expected_fields(self, app_client):
        token = _register_and_login(app_client, "jd_fields@example.com")
        data = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        assert "id" in data
        assert data["title"] == VALID_JD["title"]
        assert data["company"] == VALID_JD["company"]
        assert data["description_text"] == VALID_JD["description_text"]
        assert "user_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_without_company_succeeds(self, app_client):
        token = _register_and_login(app_client, "jd_nocompany@example.com")
        payload = {**VALID_JD, "company": None}
        resp = app_client.post(JD_URL, json=payload, headers=_auth(token))
        assert resp.status_code == 201
        assert resp.json()["company"] is None

    def test_create_sets_correct_user_id(self, app_client):
        token = _register_and_login(app_client, "jd_uid@example.com")
        me = app_client.get("/api/v1/auth/me", headers=_auth(token)).json()
        data = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        assert data["user_id"] == me["id"]

    def test_create_missing_title_returns_422(self, app_client):
        token = _register_and_login(app_client, "jd_notitle@example.com")
        payload = {k: v for k, v in VALID_JD.items() if k != "title"}
        resp = app_client.post(JD_URL, json=payload, headers=_auth(token))
        assert resp.status_code == 422

    def test_create_missing_description_text_returns_422(self, app_client):
        token = _register_and_login(app_client, "jd_nodesc@example.com")
        payload = {k: v for k, v in VALID_JD.items() if k != "description_text"}
        resp = app_client.post(JD_URL, json=payload, headers=_auth(token))
        assert resp.status_code == 422

    def test_create_short_description_returns_422(self, app_client):
        """description_text must be at least 20 characters."""
        token = _register_and_login(app_client, "jd_shortdesc@example.com")
        payload = {**VALID_JD, "description_text": "Too short."}
        resp = app_client.post(JD_URL, json=payload, headers=_auth(token))
        assert resp.status_code == 422

    def test_create_empty_title_returns_422(self, app_client):
        token = _register_and_login(app_client, "jd_emptytitle@example.com")
        payload = {**VALID_JD, "title": ""}
        resp = app_client.post(JD_URL, json=payload, headers=_auth(token))
        assert resp.status_code == 422

    def test_create_strips_company_whitespace(self, app_client):
        token = _register_and_login(app_client, "jd_strip@example.com")
        payload = {**VALID_JD, "company": "  ACME  "}
        data = app_client.post(JD_URL, json=payload, headers=_auth(token)).json()
        assert data["company"] == "ACME"


# ---------------------------------------------------------------------------
# 3. List — ownership isolation
# ---------------------------------------------------------------------------

class TestListJobDescriptions:
    def test_list_returns_200(self, app_client):
        token = _register_and_login(app_client, "jd_list@example.com")
        resp = app_client.get(JD_URL, headers=_auth(token))
        assert resp.status_code == 200

    def test_list_empty_for_new_user(self, app_client):
        token = _register_and_login(app_client, "jd_listempty@example.com")
        data = app_client.get(JD_URL, headers=_auth(token)).json()
        assert data == []

    def test_list_returns_created_jds(self, app_client):
        token = _register_and_login(app_client, "jd_listcount@example.com")
        app_client.post(JD_URL, json=VALID_JD, headers=_auth(token))
        app_client.post(JD_URL, json={**VALID_JD, "title": "Junior Dev"}, headers=_auth(token))
        data = app_client.get(JD_URL, headers=_auth(token)).json()
        assert len(data) == 2

    def test_list_does_not_include_description_text(self, app_client):
        """List response should omit description_text to keep payload lean."""
        token = _register_and_login(app_client, "jd_listlean@example.com")
        app_client.post(JD_URL, json=VALID_JD, headers=_auth(token))
        data = app_client.get(JD_URL, headers=_auth(token)).json()
        assert len(data) == 1
        assert "description_text" not in data[0]

    def test_list_isolates_users(self, app_client):
        """User A should not see User B's job descriptions."""
        token_a = _register_and_login(app_client, "jd_isola@example.com")
        token_b = _register_and_login(app_client, "jd_isolb@example.com")
        app_client.post(JD_URL, json=VALID_JD, headers=_auth(token_a))
        data_b = app_client.get(JD_URL, headers=_auth(token_b)).json()
        assert data_b == []

    def test_list_ordered_newest_first(self, app_client):
        token = _register_and_login(app_client, "jd_order@example.com")
        app_client.post(JD_URL, json={**VALID_JD, "title": "First"}, headers=_auth(token))
        app_client.post(JD_URL, json={**VALID_JD, "title": "Second"}, headers=_auth(token))
        data = app_client.get(JD_URL, headers=_auth(token)).json()
        # newest first: "Second" should appear before "First"
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"


# ---------------------------------------------------------------------------
# 4. Get detail
# ---------------------------------------------------------------------------

class TestGetJobDescription:
    def test_get_returns_200(self, app_client):
        token = _register_and_login(app_client, "jd_getok@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        resp = app_client.get(f"{JD_URL}/{created['id']}", headers=_auth(token))
        assert resp.status_code == 200

    def test_get_includes_description_text(self, app_client):
        token = _register_and_login(app_client, "jd_gettext@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        data = app_client.get(f"{JD_URL}/{created['id']}", headers=_auth(token)).json()
        assert data["description_text"] == VALID_JD["description_text"]

    def test_get_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "jd_get404@example.com")
        resp = app_client.get(f"{JD_URL}/99999", headers=_auth(token))
        assert resp.status_code == 404

    def test_get_another_users_jd_returns_404(self, app_client):
        """User B should not be able to get User A's job description."""
        token_a = _register_and_login(app_client, "jd_owna@example.com")
        token_b = _register_and_login(app_client, "jd_ownb@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token_a)).json()
        resp = app_client.get(f"{JD_URL}/{created['id']}", headers=_auth(token_b))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. Update (PUT)
# ---------------------------------------------------------------------------

class TestUpdateJobDescription:
    UPDATED_JD = {
        "title": "Lead Backend Engineer",
        "company": "Globex",
        "description_text": (
            "Seeking a lead backend engineer with deep expertise in Python, "
            "FastAPI, PostgreSQL, Docker, and microservices architecture. "
            "Experience with Kubernetes and Terraform is highly desired."
        ),
    }

    def test_update_returns_200(self, app_client):
        token = _register_and_login(app_client, "jd_putok@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        resp = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=self.UPDATED_JD,
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_update_replaces_all_fields(self, app_client):
        token = _register_and_login(app_client, "jd_putfields@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        data = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=self.UPDATED_JD,
            headers=_auth(token),
        ).json()
        assert data["title"] == self.UPDATED_JD["title"]
        assert data["company"] == self.UPDATED_JD["company"]
        assert data["description_text"] == self.UPDATED_JD["description_text"]
        assert data["id"] == created["id"]

    def test_update_without_company_sets_null(self, app_client):
        token = _register_and_login(app_client, "jd_putnocompany@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        payload = {**self.UPDATED_JD, "company": None}
        data = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=payload,
            headers=_auth(token),
        ).json()
        assert data["company"] is None

    def test_update_strips_company_whitespace(self, app_client):
        token = _register_and_login(app_client, "jd_putstrip@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        payload = {**self.UPDATED_JD, "company": "  Globex  "}
        data = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=payload,
            headers=_auth(token),
        ).json()
        assert data["company"] == "Globex"

    def test_update_missing_title_returns_422(self, app_client):
        token = _register_and_login(app_client, "jd_putnotitle@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        payload = {k: v for k, v in self.UPDATED_JD.items() if k != "title"}
        resp = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=payload,
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_update_missing_description_text_returns_422(self, app_client):
        token = _register_and_login(app_client, "jd_putnodesc@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        payload = {k: v for k, v in self.UPDATED_JD.items() if k != "description_text"}
        resp = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=payload,
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_update_short_description_returns_422(self, app_client):
        token = _register_and_login(app_client, "jd_putshortdesc@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        payload = {**self.UPDATED_JD, "description_text": "Too short."}
        resp = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=payload,
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_update_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "jd_put404@example.com")
        resp = app_client.put(
            f"{JD_URL}/99999",
            json=self.UPDATED_JD,
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_update_another_users_jd_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "jd_putowna@example.com")
        token_b = _register_and_login(app_client, "jd_putownb@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token_a)).json()
        resp = app_client.put(
            f"{JD_URL}/{created['id']}",
            json=self.UPDATED_JD,
            headers=_auth(token_b),
        )
        assert resp.status_code == 404

    def test_update_does_not_change_other_jds(self, app_client):
        """Updating one JD must not affect other JDs owned by the same user."""
        token = _register_and_login(app_client, "jd_putisolate@example.com")
        jd1 = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        jd2 = app_client.post(
            JD_URL, json={**VALID_JD, "title": "Original Title 2"}, headers=_auth(token)
        ).json()
        app_client.put(
            f"{JD_URL}/{jd1['id']}",
            json=self.UPDATED_JD,
            headers=_auth(token),
        )
        # jd2 should be unchanged
        jd2_after = app_client.get(
            f"{JD_URL}/{jd2['id']}", headers=_auth(token)
        ).json()
        assert jd2_after["title"] == "Original Title 2"


# ---------------------------------------------------------------------------
# 6. Delete
# ---------------------------------------------------------------------------

class TestDeleteJobDescription:
    def test_delete_returns_204(self, app_client):
        token = _register_and_login(app_client, "jd_delok@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        resp = app_client.delete(
            f"{JD_URL}/{created['id']}", headers=_auth(token)
        )
        assert resp.status_code == 204

    def test_delete_response_body_is_empty(self, app_client):
        token = _register_and_login(app_client, "jd_delbody@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        resp = app_client.delete(
            f"{JD_URL}/{created['id']}", headers=_auth(token)
        )
        assert resp.text == ""

    def test_delete_makes_get_return_404(self, app_client):
        token = _register_and_login(app_client, "jd_delverify@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        app_client.delete(f"{JD_URL}/{created['id']}", headers=_auth(token))
        resp = app_client.get(f"{JD_URL}/{created['id']}", headers=_auth(token))
        assert resp.status_code == 404

    def test_delete_makes_list_empty(self, app_client):
        token = _register_and_login(app_client, "jd_dellist@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        app_client.delete(f"{JD_URL}/{created['id']}", headers=_auth(token))
        data = app_client.get(JD_URL, headers=_auth(token)).json()
        assert data == []

    def test_delete_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "jd_del404@example.com")
        resp = app_client.delete(f"{JD_URL}/99999", headers=_auth(token))
        assert resp.status_code == 404

    def test_delete_another_users_jd_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "jd_delowna@example.com")
        token_b = _register_and_login(app_client, "jd_delownb@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token_a)).json()
        resp = app_client.delete(
            f"{JD_URL}/{created['id']}", headers=_auth(token_b)
        )
        assert resp.status_code == 404

    def test_delete_another_users_jd_preserves_record(self, app_client):
        """After a failed cross-user delete, the original owner can still see the JD."""
        token_a = _register_and_login(app_client, "jd_delowna2@example.com")
        token_b = _register_and_login(app_client, "jd_delownb2@example.com")
        created = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token_a)).json()
        app_client.delete(f"{JD_URL}/{created['id']}", headers=_auth(token_b))
        resp = app_client.get(
            f"{JD_URL}/{created['id']}", headers=_auth(token_a)
        )
        assert resp.status_code == 200

    def test_delete_one_does_not_affect_others(self, app_client):
        token = _register_and_login(app_client, "jd_delone@example.com")
        jd1 = app_client.post(JD_URL, json=VALID_JD, headers=_auth(token)).json()
        jd2 = app_client.post(
            JD_URL, json={**VALID_JD, "title": "Second JD"}, headers=_auth(token)
        ).json()
        app_client.delete(f"{JD_URL}/{jd1['id']}", headers=_auth(token))
        data = app_client.get(JD_URL, headers=_auth(token)).json()
        assert len(data) == 1
        assert data[0]["title"] == "Second JD"


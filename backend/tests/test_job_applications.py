"""Tests for job-application endpoints (CRUD operations).

Coverage:
- POST   /api/v1/job-applications       → create
- GET    /api/v1/job-applications        → list
- GET    /api/v1/job-applications/{id}   → detail
- PUT    /api/v1/job-applications/{id}   → update
- DELETE /api/v1/job-applications/{id}   → delete

All tests verify authentication, ownership enforcement, and proper error handling.

All tests use the `app_client` fixture and the `_register_and_login` helper
so that users are created in the same database the HTTP client uses.
"""

JA_URL = "/api/v1/job-applications"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

VALID_PAYLOAD = {
    "company_name": "Acme Corp",
    "role_title": "Senior Python Developer",
    "status": "applied",
    "job_url": "https://example.com/job",
    "notes": "Looks promising",
    "deadline": "2026-11-15T00:00:00Z",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, email: str, password: str = "TestPass123!") -> str:
    """Register a user via the API and return their Bearer token."""
    client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    resp = client.post(LOGIN_URL, json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_app(client, token, payload=None):
    """Create a job application and return the response JSON."""
    if payload is None:
        payload = VALID_PAYLOAD
    return client.post(JA_URL, json=payload, headers=_auth(token)).json()


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------


class TestAuthGuard:
    def test_create_without_token_returns_401(self, app_client):
        resp = app_client.post(JA_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 401

    def test_list_without_token_returns_401(self, app_client):
        resp = app_client.get(JA_URL)
        assert resp.status_code == 401

    def test_get_without_token_returns_401(self, app_client):
        resp = app_client.get(f"{JA_URL}/1")
        assert resp.status_code == 401

    def test_update_without_token_returns_401(self, app_client):
        resp = app_client.put(f"{JA_URL}/1", json={"status": "offer"})
        assert resp.status_code == 401

    def test_delete_without_token_returns_401(self, app_client):
        resp = app_client.delete(f"{JA_URL}/1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Create — POST /api/v1/job-applications
# ---------------------------------------------------------------------------


class TestCreateJobApplication:
    def test_create_returns_201(self, app_client):
        token = _register_and_login(app_client, "ja_create@example.com")
        resp = app_client.post(JA_URL, json=VALID_PAYLOAD, headers=_auth(token))
        assert resp.status_code == 201

    def test_create_response_has_expected_fields(self, app_client):
        token = _register_and_login(app_client, "ja_fields@example.com")
        data = app_client.post(JA_URL, json=VALID_PAYLOAD, headers=_auth(token)).json()
        assert "id" in data
        assert data["company_name"] == "Acme Corp"
        assert data["role_title"] == "Senior Python Developer"
        assert data["status"] == "applied"
        assert data["job_url"] == "https://example.com/job"
        assert data["notes"] == "Looks promising"
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_minimal_fields(self, app_client):
        """Only company_name and role_title are required; status defaults to 'applied'."""
        token = _register_and_login(app_client, "ja_minimal@example.com")
        resp = app_client.post(
            JA_URL,
            json={"company_name": "Minimal Inc", "role_title": "Developer"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_name"] == "Minimal Inc"
        assert data["status"] == "applied"
        assert data["job_url"] is None
        assert data["notes"] is None
        assert data["deadline"] is None

    def test_create_invalid_status_returns_422(self, app_client):
        token = _register_and_login(app_client, "ja_badstatus@example.com")
        resp = app_client.post(
            JA_URL,
            json={
                "company_name": "Bad Status Corp",
                "role_title": "Developer",
                "status": "invalid_status",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_create_missing_company_name_returns_422(self, app_client):
        token = _register_and_login(app_client, "ja_nocompany@example.com")
        resp = app_client.post(
            JA_URL,
            json={"role_title": "Developer"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_create_missing_role_title_returns_422(self, app_client):
        token = _register_and_login(app_client, "ja_norole@example.com")
        resp = app_client.post(
            JA_URL,
            json={"company_name": "Only Company"},
            headers=_auth(token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. List — GET /api/v1/job-applications
# ---------------------------------------------------------------------------


class TestListJobApplications:
    def test_list_returns_200(self, app_client):
        token = _register_and_login(app_client, "ja_list@example.com")
        resp = app_client.get(JA_URL, headers=_auth(token))
        assert resp.status_code == 200

    def test_list_empty_for_new_user(self, app_client):
        token = _register_and_login(app_client, "ja_listempty@example.com")
        data = app_client.get(JA_URL, headers=_auth(token)).json()
        assert data == []

    def test_list_returns_created_apps(self, app_client):
        token = _register_and_login(app_client, "ja_listcount@example.com")
        _create_app(app_client, token)
        _create_app(app_client, token, {**VALID_PAYLOAD, "company_name": "Second Co"})
        data = app_client.get(JA_URL, headers=_auth(token)).json()
        assert len(data) == 2

    def test_list_ordered_newest_first(self, app_client):
        token = _register_and_login(app_client, "ja_order@example.com")
        _create_app(app_client, token, {**VALID_PAYLOAD, "company_name": "First Co"})
        _create_app(app_client, token, {**VALID_PAYLOAD, "company_name": "Second Co"})
        data = app_client.get(JA_URL, headers=_auth(token)).json()
        assert data[0]["company_name"] == "Second Co"
        assert data[1]["company_name"] == "First Co"

    def test_list_isolates_users(self, app_client):
        """User B should not see User A's applications."""
        token_a = _register_and_login(app_client, "ja_isola@example.com")
        token_b = _register_and_login(app_client, "ja_isolb@example.com")
        _create_app(app_client, token_a)
        data_b = app_client.get(JA_URL, headers=_auth(token_b)).json()
        assert data_b == []


# ---------------------------------------------------------------------------
# 4. Get detail — GET /api/v1/job-applications/{id}
# ---------------------------------------------------------------------------


class TestGetJobApplication:
    def test_get_returns_200(self, app_client):
        token = _register_and_login(app_client, "ja_getok@example.com")
        created = _create_app(app_client, token)
        resp = app_client.get(f"{JA_URL}/{created['id']}", headers=_auth(token))
        assert resp.status_code == 200

    def test_get_returns_correct_data(self, app_client):
        token = _register_and_login(app_client, "ja_getdata@example.com")
        created = _create_app(app_client, token)
        data = app_client.get(f"{JA_URL}/{created['id']}", headers=_auth(token)).json()
        assert data["id"] == created["id"]
        assert data["company_name"] == "Acme Corp"
        assert data["role_title"] == "Senior Python Developer"

    def test_get_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "ja_get404@example.com")
        resp = app_client.get(f"{JA_URL}/99999", headers=_auth(token))
        assert resp.status_code == 404

    def test_get_another_users_app_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "ja_owna@example.com")
        token_b = _register_and_login(app_client, "ja_ownb@example.com")
        created = _create_app(app_client, token_a)
        resp = app_client.get(f"{JA_URL}/{created['id']}", headers=_auth(token_b))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. Update — PUT /api/v1/job-applications/{id}
# ---------------------------------------------------------------------------


class TestUpdateJobApplication:
    def test_update_returns_200(self, app_client):
        token = _register_and_login(app_client, "ja_putok@example.com")
        created = _create_app(app_client, token)
        resp = app_client.put(
            f"{JA_URL}/{created['id']}",
            json={"status": "offer", "notes": "Got an offer!"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_update_partial_fields(self, app_client):
        """Only provided fields are changed; others remain the same."""
        token = _register_and_login(app_client, "ja_putpartial@example.com")
        created = _create_app(app_client, token)
        data = app_client.put(
            f"{JA_URL}/{created['id']}",
            json={"status": "rejected"},
            headers=_auth(token),
        ).json()
        assert data["status"] == "rejected"
        assert data["notes"] == "Looks promising"
        assert data["company_name"] == "Acme Corp"

    def test_update_invalid_status_returns_422(self, app_client):
        token = _register_and_login(app_client, "ja_putbadstatus@example.com")
        created = _create_app(app_client, token)
        resp = app_client.put(
            f"{JA_URL}/{created['id']}",
            json={"status": "bad_status"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_update_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "ja_put404@example.com")
        resp = app_client.put(
            f"{JA_URL}/99999",
            json={"status": "offer"},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_update_another_users_app_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "ja_putowna@example.com")
        token_b = _register_and_login(app_client, "ja_putownb@example.com")
        created = _create_app(app_client, token_a)
        resp = app_client.put(
            f"{JA_URL}/{created['id']}",
            json={"status": "archived"},
            headers=_auth(token_b),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Delete — DELETE /api/v1/job-applications/{id}
# ---------------------------------------------------------------------------


class TestDeleteJobApplication:
    def test_delete_returns_204(self, app_client):
        token = _register_and_login(app_client, "ja_delok@example.com")
        created = _create_app(app_client, token)
        resp = app_client.delete(f"{JA_URL}/{created['id']}", headers=_auth(token))
        assert resp.status_code == 204

    def test_delete_response_body_is_empty(self, app_client):
        token = _register_and_login(app_client, "ja_delbody@example.com")
        created = _create_app(app_client, token)
        resp = app_client.delete(f"{JA_URL}/{created['id']}", headers=_auth(token))
        assert resp.text == ""

    def test_delete_makes_get_return_404(self, app_client):
        token = _register_and_login(app_client, "ja_delverify@example.com")
        created = _create_app(app_client, token)
        app_client.delete(f"{JA_URL}/{created['id']}", headers=_auth(token))
        resp = app_client.get(f"{JA_URL}/{created['id']}", headers=_auth(token))
        assert resp.status_code == 404

    def test_delete_makes_list_empty(self, app_client):
        token = _register_and_login(app_client, "ja_dellist@example.com")
        created = _create_app(app_client, token)
        app_client.delete(f"{JA_URL}/{created['id']}", headers=_auth(token))
        data = app_client.get(JA_URL, headers=_auth(token)).json()
        assert data == []

    def test_delete_nonexistent_returns_404(self, app_client):
        token = _register_and_login(app_client, "ja_del404@example.com")
        resp = app_client.delete(f"{JA_URL}/99999", headers=_auth(token))
        assert resp.status_code == 404

    def test_delete_another_users_app_returns_404(self, app_client):
        token_a = _register_and_login(app_client, "ja_delowna@example.com")
        token_b = _register_and_login(app_client, "ja_delownb@example.com")
        created = _create_app(app_client, token_a)
        resp = app_client.delete(f"{JA_URL}/{created['id']}", headers=_auth(token_b))
        assert resp.status_code == 404

    def test_delete_another_users_app_preserves_record(self, app_client):
        """After a failed cross-user delete, the original owner can still see the app."""
        token_a = _register_and_login(app_client, "ja_delowna2@example.com")
        token_b = _register_and_login(app_client, "ja_delownb2@example.com")
        created = _create_app(app_client, token_a)
        app_client.delete(f"{JA_URL}/{created['id']}", headers=_auth(token_b))
        resp = app_client.get(f"{JA_URL}/{created['id']}", headers=_auth(token_a))
        assert resp.status_code == 200

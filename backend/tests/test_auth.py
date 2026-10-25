"""Comprehensive tests for the authentication system.

Tests are organised into four sections:
1. Security utilities  — hash_password, verify_password, JWT create/decode
2. POST /auth/register — happy path, duplicate email, validation errors
3. POST /auth/login    — happy path, wrong password, unknown email, inactive
4. GET  /auth/me       — valid token, missing token, invalid token, expired

All tests use the `app_client` fixture from conftest.py which overrides the
`get_db` dependency with an isolated in-memory SQLite database, so no
PostgreSQL connection is required.
"""

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"

VALID_EMAIL = "alice@example.com"
VALID_PASSWORD = "S3curePass!"
VALID_NAME = "Alice Example"


def _register(client, email=VALID_EMAIL, password=VALID_PASSWORD, full_name=VALID_NAME):
    """POST /register shorthand used across many tests."""
    return client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "full_name": full_name},
    )


def _login(client, email=VALID_EMAIL, password=VALID_PASSWORD):
    """POST /login shorthand used across many tests."""
    return client.post(
        LOGIN_URL,
        json={"email": email, "password": password},
    )


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Section 1 — Security utilities (pure unit tests, no HTTP)
# ===========================================================================


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"

    def test_same_password_produces_different_hashes(self):
        """bcrypt uses a random salt so the same password never hashes identically."""
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2

    def test_verify_password_correct(self):
        hashed = hash_password("correct_horse")
        assert verify_password("correct_horse", hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("correct_horse")
        assert verify_password("wrong_horse", hashed) is False

    def test_verify_password_empty_string_fails(self):
        hashed = hash_password("real_password")
        assert verify_password("", hashed) is False


class TestJwtTokens:
    def test_create_and_decode_round_trip(self):
        token = create_access_token(data={"sub": "user@example.com"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"

    def test_decode_returns_none_for_garbage(self):
        result = decode_access_token("this.is.not.a.jwt")
        assert result is None

    def test_decode_returns_none_for_empty_string(self):
        result = decode_access_token("")
        assert result is None

    def test_expired_token_returns_none(self):
        """A token with a negative expiry should fail verification."""
        token = create_access_token(
            data={"sub": "user@example.com"},
            expires_delta=timedelta(seconds=-1),
        )
        result = decode_access_token(token)
        assert result is None

    def test_token_with_custom_expiry(self):
        """Custom expiry should be honoured."""
        token = create_access_token(
            data={"sub": "user@example.com"},
            expires_delta=timedelta(hours=2),
        )
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"

    def test_token_tampered_signature_rejected(self):
        """Replacing the signature segment must cause verification to fail."""
        token = create_access_token(data={"sub": "user@example.com"})
        # JWT structure: header.payload.signature — replace the signature entirely
        parts = token.split(".")
        parts[2] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        tampered = ".".join(parts)
        result = decode_access_token(tampered)
        assert result is None

    def test_arbitrary_payload_preserved(self):
        token = create_access_token(data={"sub": "x@y.com", "role": "admin"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"


# ===========================================================================
# Section 2 — POST /api/v1/auth/register
# ===========================================================================


class TestRegister:
    def test_register_returns_201(self, app_client):
        response = _register(app_client)
        assert response.status_code == 201

    def test_register_returns_user_data(self, app_client):
        response = _register(app_client)
        data = response.json()
        assert data["email"] == VALID_EMAIL
        assert data["full_name"] == VALID_NAME
        assert data["is_active"] is True

    def test_register_assigns_id(self, app_client):
        response = _register(app_client)
        assert "id" in response.json()
        assert isinstance(response.json()["id"], int)

    def test_register_does_not_return_password_hash(self, app_client):
        response = _register(app_client)
        data = response.json()
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_normalises_email_to_lowercase(self, app_client):
        response = app_client.post(
            REGISTER_URL,
            json={"email": "Alice@Example.COM", "password": VALID_PASSWORD, "full_name": VALID_NAME},
        )
        assert response.status_code == 201
        assert response.json()["email"] == "alice@example.com"

    def test_register_strips_whitespace_from_name(self, app_client):
        response = app_client.post(
            REGISTER_URL,
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD, "full_name": "  Bob  "},
        )
        assert response.status_code == 201
        assert response.json()["full_name"] == "Bob"

    def test_register_duplicate_email_returns_409(self, app_client):
        _register(app_client)  # first registration
        response = _register(app_client)  # same email again
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_register_duplicate_is_case_insensitive(self, app_client):
        """Upper-cased duplicate should still be rejected after normalisation."""
        _register(app_client)
        response = app_client.post(
            REGISTER_URL,
            json={"email": "ALICE@EXAMPLE.COM", "password": VALID_PASSWORD, "full_name": VALID_NAME},
        )
        assert response.status_code == 409

    def test_register_invalid_email_returns_422(self, app_client):
        response = app_client.post(
            REGISTER_URL,
            json={"email": "not-an-email", "password": VALID_PASSWORD, "full_name": VALID_NAME},
        )
        assert response.status_code == 422

    def test_register_short_password_returns_422(self, app_client):
        response = app_client.post(
            REGISTER_URL,
            json={"email": VALID_EMAIL, "password": "short", "full_name": VALID_NAME},
        )
        assert response.status_code == 422

    def test_register_empty_name_returns_422(self, app_client):
        response = app_client.post(
            REGISTER_URL,
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD, "full_name": ""},
        )
        assert response.status_code == 422

    def test_register_missing_fields_returns_422(self, app_client):
        response = app_client.post(REGISTER_URL, json={"email": VALID_EMAIL})
        assert response.status_code == 422


# ===========================================================================
# Section 3 — POST /api/v1/auth/login
# ===========================================================================


class TestLogin:
    def test_login_returns_200_with_valid_credentials(self, app_client):
        _register(app_client)
        response = _login(app_client)
        assert response.status_code == 200

    def test_login_returns_access_token(self, app_client):
        _register(app_client)
        data = _login(app_client).json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 20

    def test_login_returns_bearer_token_type(self, app_client):
        _register(app_client)
        data = _login(app_client).json()
        assert data["token_type"] == "bearer"

    def test_login_token_is_a_valid_jwt(self, app_client):
        """The token returned by /login must decode correctly."""
        _register(app_client)
        token = _login(app_client).json()["access_token"]
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == VALID_EMAIL

    def test_login_wrong_password_returns_401(self, app_client):
        _register(app_client)
        response = _login(app_client, password="WrongPassword!")
        assert response.status_code == 401

    def test_login_unknown_email_returns_401(self, app_client):
        response = _login(app_client, email="nobody@example.com")
        assert response.status_code == 401

    def test_login_wrong_password_error_message_is_generic(self, app_client):
        """Don't reveal whether the email exists — both errors look the same."""
        _register(app_client)
        resp_wrong_pw = _login(app_client, password="WrongPassword!")
        resp_unknown = _login(app_client, email="nobody@example.com")
        assert resp_wrong_pw.json()["detail"] == resp_unknown.json()["detail"]

    def test_login_email_is_case_insensitive(self, app_client):
        """Registered with lowercase, login with uppercase should still succeed."""
        _register(app_client)
        response = app_client.post(
            LOGIN_URL,
            json={"email": "ALICE@EXAMPLE.COM", "password": VALID_PASSWORD},
        )
        assert response.status_code == 200

    def test_login_inactive_user_returns_401(self, app_client):
        """Disabled accounts should be rejected at login."""
        # Register normally
        _register(app_client)
        # Manually deactivate the user via the DB override
        from app.database import get_db
        db = next(app_client.app.dependency_overrides[get_db]())
        from app.models import User
        user = db.query(User).filter(User.email == VALID_EMAIL).first()
        user.is_active = False
        db.commit()
        db.close()

        response = _login(app_client)
        assert response.status_code == 401

    def test_login_missing_email_returns_422(self, app_client):
        response = app_client.post(LOGIN_URL, json={"password": VALID_PASSWORD})
        assert response.status_code == 422

    def test_login_missing_password_returns_422(self, app_client):
        response = app_client.post(LOGIN_URL, json={"email": VALID_EMAIL})
        assert response.status_code == 422


# ===========================================================================
# Section 4 — GET /api/v1/auth/me
# ===========================================================================


class TestGetMe:
    def _get_token(self, client) -> str:
        """Register + login, return the access token string."""
        _register(client)
        return _login(client).json()["access_token"]

    def test_me_returns_200_with_valid_token(self, app_client):
        token = self._get_token(app_client)
        response = app_client.get(ME_URL, headers=_auth_header(token))
        assert response.status_code == 200

    def test_me_returns_correct_user_data(self, app_client):
        token = self._get_token(app_client)
        data = app_client.get(ME_URL, headers=_auth_header(token)).json()
        assert data["email"] == VALID_EMAIL
        assert data["full_name"] == VALID_NAME
        assert data["is_active"] is True

    def test_me_does_not_expose_password_hash(self, app_client):
        token = self._get_token(app_client)
        data = app_client.get(ME_URL, headers=_auth_header(token)).json()
        assert "password" not in data
        assert "password_hash" not in data

    def test_me_no_token_returns_401(self, app_client):
        response = app_client.get(ME_URL)
        assert response.status_code == 401

    def test_me_invalid_token_returns_401(self, app_client):
        response = app_client.get(ME_URL, headers=_auth_header("not.a.real.token"))
        assert response.status_code == 401

    def test_me_expired_token_returns_401(self, app_client):
        _register(app_client)
        expired_token = create_access_token(
            data={"sub": VALID_EMAIL},
            expires_delta=timedelta(seconds=-1),
        )
        response = app_client.get(ME_URL, headers=_auth_header(expired_token))
        assert response.status_code == 401

    def test_me_tampered_token_returns_401(self, app_client):
        """Replacing the signature segment entirely must be rejected."""
        token = self._get_token(app_client)
        # JWT structure: header.payload.signature  — replace the signature with garbage
        parts = token.split(".")
        parts[2] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        tampered = ".".join(parts)
        response = app_client.get(ME_URL, headers=_auth_header(tampered))
        assert response.status_code == 401

    def test_me_token_with_nonexistent_user_returns_401(self, app_client):
        """A valid JWT for an email that was never registered must be rejected."""
        ghost_token = create_access_token(data={"sub": "ghost@example.com"})
        response = app_client.get(ME_URL, headers=_auth_header(ghost_token))
        assert response.status_code == 401

    def test_me_token_missing_sub_claim_returns_401(self, app_client):
        """Tokens without a 'sub' claim must be rejected by the dependency."""
        bad_token = create_access_token(data={"user_id": 42})  # no 'sub'
        response = app_client.get(ME_URL, headers=_auth_header(bad_token))
        assert response.status_code == 401

    def test_me_inactive_user_returns_401(self, app_client):
        """A valid token for a deactivated account should be rejected."""
        token = self._get_token(app_client)

        from app.database import get_db
        db = next(app_client.app.dependency_overrides[get_db]())
        from app.models import User
        user = db.query(User).filter(User.email == VALID_EMAIL).first()
        user.is_active = False
        db.commit()
        db.close()

        response = app_client.get(ME_URL, headers=_auth_header(token))
        assert response.status_code == 401

    def test_me_error_message_matches_dependency_wording(self, app_client):
        """The 401 detail must match what get_current_user raises."""
        response = app_client.get(ME_URL, headers=_auth_header("bad.token.here"))
        assert "invalid" in response.json()["detail"].lower()

    def test_full_register_login_me_flow(self, app_client):
        """End-to-end: register → login → /me should all succeed consistently."""
        reg = _register(app_client)
        assert reg.status_code == 201

        token = _login(app_client).json()["access_token"]
        assert token

        me = app_client.get(ME_URL, headers=_auth_header(token)).json()
        assert me["email"] == VALID_EMAIL
        assert me["id"] == reg.json()["id"]



# ---------------------------------------------------------------------------
# PUT /auth/me — profile update tests
# ---------------------------------------------------------------------------

ME_URL = "/api/v1/auth/me"


class TestUpdateMe:
    """Verify PUT /auth/me profile-update behavior."""

    def _register_and_get_token(self, client, email: str) -> str:
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "TestPass123!", "full_name": "Test User"},
        )
        return client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "TestPass123!"},
        ).json()["access_token"]

    def test_update_name_only(self, app_client):
        token = self._register_and_get_token(app_client, "upd_name@example.com")
        resp = app_client.put(
            ME_URL,
            json={"full_name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    def test_update_password_success(self, app_client):
        token = self._register_and_get_token(app_client, "upd_pw@example.com")
        resp = app_client.put(
            ME_URL,
            json={"current_password": "TestPass123!", "new_password": "NewPass456!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Verify new password works
        login = app_client.post(
            "/api/v1/auth/login",
            json={"email": "upd_pw@example.com", "password": "NewPass456!"},
        )
        assert login.status_code == 200

    def test_update_password_wrong_current_returns_400(self, app_client):
        token = self._register_and_get_token(app_client, "upd_pwbad@example.com")
        resp = app_client.put(
            ME_URL,
            json={"current_password": "WrongPassword!", "new_password": "NewPass456!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_update_new_password_without_current_returns_400(self, app_client):
        token = self._register_and_get_token(app_client, "upd_nopw@example.com")
        resp = app_client.put(
            ME_URL,
            json={"new_password": "NewPass456!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_update_no_fields_is_noop(self, app_client):
        token = self._register_and_get_token(app_client, "upd_noop@example.com")
        before = app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}).json()
        resp = app_client.put(
            ME_URL,
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == before["full_name"]

    def test_update_without_token_returns_401(self, app_client):
        resp = app_client.put(ME_URL, json={"full_name": "Hacker"})
        assert resp.status_code == 401

    def test_response_never_includes_password_hash(self, app_client):
        token = self._register_and_get_token(app_client, "upd_nopwhash@example.com")
        resp = app_client.put(
            ME_URL,
            json={"full_name": "Safe Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        assert "password_hash" not in body
        assert "password" not in body
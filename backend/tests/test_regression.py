"""Regression checks covering the most critical end-to-end behaviors.

These complement the existing unit tests with integration-style assertions
that span multiple layers (routing → auth → response shape).  They run
against the same in-memory SQLite TestClient used by other tests.
"""
import io
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Suppress the dev-key warning during these tests
logging.disable(logging.WARNING)

client = TestClient(app)


class TestRootEndpoint:
    def test_root_returns_json(self):
        """/ returns JSON (not HTML) when SERVE_FRONTEND is false."""
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["docs"] == "/docs"

    def test_root_content_type_is_json(self):
        r = client.get("/")
        assert "application/json" in r.headers.get("content-type", "")


class TestApiRouting:
    def test_health_returns_healthy(self):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_docs_accessible(self):
        r = client.get("/docs")
        assert r.status_code == 200

    def test_unknown_api_route_returns_json_404(self):
        """Unknown /api/v1/* paths must return JSON 404, never HTML."""
        r = client.get("/api/v1/does-not-exist")
        assert r.status_code == 404
        data = r.json()
        assert "detail" in data
        assert "text/html" not in r.headers.get("content-type", "")

    def test_unknown_top_level_path_returns_404(self):
        """Unknown top-level paths return 404 when frontend serving is off."""
        r = client.get("/some-random-page")
        assert r.status_code == 404


class TestAuthentication:
    def test_register_invalid_email_422(self):
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "notanemail", "password": "password123", "full_name": "Test"},
        )
        assert r.status_code == 422

    def test_register_short_password_422(self):
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "short", "full_name": "Test"},
        )
        assert r.status_code == 422

    def test_login_wrong_credentials_401_generic_message(self):
        """Wrong credentials return 401 with a message that doesn't reveal which field was wrong."""
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass"},
        )
        assert r.status_code == 401
        detail = r.json()["detail"]
        # Generic — cannot tell if user exists or password is wrong
        assert "Incorrect" in detail
        assert "password_hash" not in detail
        assert "secret" not in detail.lower()

    def test_protected_endpoint_without_token_401(self):
        r = client.get("/api/v1/resumes")
        assert r.status_code == 401

    def test_protected_endpoint_with_invalid_token_401(self):
        r = client.get(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert r.status_code == 401


class TestUploadValidation:
    def test_upload_with_wrong_extension_rejected(self, app_client):
        """Uploading a .exe file is rejected before auth even matters."""
        # Need a real auth'd client to reach file validation
        # Register + login
        app_client.post(
            "/api/v1/auth/register",
            json={"email": "upload_test@example.com", "password": "testpassword", "full_name": "Tester"},
        )
        login_r = app_client.post(
            "/api/v1/auth/login",
            json={"email": "upload_test@example.com", "password": "testpassword"},
        )
        token = login_r.json()["access_token"]

        r = app_client.post(
            "/api/v1/resumes",
            files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code in {400, 415}

    def test_upload_empty_file_rejected(self, app_client):
        app_client.post(
            "/api/v1/auth/register",
            json={"email": "upload_empty@example.com", "password": "testpassword", "full_name": "Tester"},
        )
        login_r = app_client.post(
            "/api/v1/auth/login",
            json={"email": "upload_empty@example.com", "password": "testpassword"},
        )
        token = login_r.json()["access_token"]

        r = app_client.post(
            "/api/v1/resumes",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code in {400, 415}

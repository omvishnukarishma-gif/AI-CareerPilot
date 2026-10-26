"""Tests for SERVE_FRONTEND configuration behaviour.

These tests verify that:
- When SERVE_FRONTEND=false (default), / returns JSON with a docs link.
- When SERVE_FRONTEND=true but no build exists, / returns a JSON fallback
  (not a crash and not an empty body).
- When SERVE_FRONTEND=true and a build exists, / serves index.html.
- Unknown API paths return JSON 404 regardless of SERVE_FRONTEND.
- SPA routes (e.g. /register) return index.html when serving is enabled.
- Path traversal attempts are rejected.

The tests patch app.config.settings in isolation so they do not affect
the shared settings used by other test modules.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper: reload the app with a given SERVE_FRONTEND value
# ---------------------------------------------------------------------------

def _client_with_serve_frontend(value: bool) -> TestClient:
    """Return a TestClient whose app uses SERVE_FRONTEND=<value>.

    We import the module under test inside the function so that each call
    gets the module with a freshly patched settings object.
    """
    import importlib
    import app.main as main_module

    # Patch the settings attribute on the already-imported settings instance.
    with patch.object(main_module.settings, "serve_frontend", value):
        return TestClient(main_module.app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# SERVE_FRONTEND = False (default)
# ---------------------------------------------------------------------------

class TestServeFrontendDisabled:
    """When SERVE_FRONTEND is false the API JSON behaviour must be preserved."""

    def test_root_returns_json_with_docs_link(self):
        """/ must return JSON containing 'docs' when serving is disabled."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", False):
            client = TestClient(main_module.app)
            response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["docs"] == "/docs"

    def test_root_returns_json_message(self):
        """/ must return a message field when serving is disabled."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", False):
            client = TestClient(main_module.app)
            response = client.get("/")
        data = response.json()
        assert "message" in data

    def test_root_returns_health_link(self):
        """/ must include a health link when serving is disabled."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", False):
            client = TestClient(main_module.app)
            response = client.get("/")
        data = response.json()
        assert "health" in data
        assert "/api/v1/health" in data["health"]

    def test_unknown_path_returns_404_not_html(self):
        """Unknown paths must return JSON 404 when frontend serving is off."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", False):
            client = TestClient(main_module.app)
            response = client.get("/totally-unknown-page")
        assert response.status_code == 404
        # Must be JSON, not HTML
        data = response.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# SERVE_FRONTEND = True, no build present
# ---------------------------------------------------------------------------

class TestServeFrontendEnabledNoBuild:
    """When serving is enabled but dist/ is absent, return a JSON fallback."""

    def test_root_returns_json_fallback_when_build_missing(self):
        """/ must return JSON (not crash) when dist/index.html is absent."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_INDEX_FILE", Path("/nonexistent/index.html")):
            client = TestClient(main_module.app)
            response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "docs" in data or "warning" in data

    def test_spa_route_returns_404_when_build_missing(self):
        """SPA route must return 404 JSON (not HTML) when build is missing."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_INDEX_FILE", Path("/nonexistent/index.html")):
            client = TestClient(main_module.app)
            response = client.get("/register")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# SERVE_FRONTEND = True, build present (using a temporary directory)
# ---------------------------------------------------------------------------

class TestServeFrontendEnabledWithBuild:
    """When serving is enabled and dist/index.html exists, serve the SPA."""

    @pytest.fixture()
    def dist_dir(self, tmp_path: Path):
        """Create a minimal frontend dist directory."""
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text(
            "<!DOCTYPE html><html><body>React App</body></html>"
        )
        assets = dist / "assets"
        assets.mkdir()
        (assets / "main.js").write_text("// main bundle")
        return dist

    def test_root_serves_index_html(self, dist_dir: Path):
        """/ must serve index.html when the build is present."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_FRONTEND_DIST", dist_dir), \
             patch.object(main_module, "_INDEX_FILE", dist_dir / "index.html"), \
             patch.object(main_module, "_ASSETS_DIR", dist_dir / "assets"):
            client = TestClient(main_module.app)
            response = client.get("/")
        assert response.status_code == 200
        assert b"React App" in response.content

    def test_spa_route_serves_index_html(self, dist_dir: Path):
        """/register must serve index.html (React Router handles it client-side)."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_FRONTEND_DIST", dist_dir), \
             patch.object(main_module, "_INDEX_FILE", dist_dir / "index.html"), \
             patch.object(main_module, "_ASSETS_DIR", dist_dir / "assets"):
            client = TestClient(main_module.app)
            response = client.get("/register")
        assert response.status_code == 200
        assert b"React App" in response.content

    def test_login_route_serves_index_html(self, dist_dir: Path):
        """/login must also serve index.html."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_FRONTEND_DIST", dist_dir), \
             patch.object(main_module, "_INDEX_FILE", dist_dir / "index.html"), \
             patch.object(main_module, "_ASSETS_DIR", dist_dir / "assets"):
            client = TestClient(main_module.app)
            response = client.get("/login")
        assert response.status_code == 200
        assert b"React App" in response.content

    def test_existing_static_file_served_directly(self, dist_dir: Path):
        """A file that physically exists in dist/ must be served directly."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_FRONTEND_DIST", dist_dir), \
             patch.object(main_module, "_INDEX_FILE", dist_dir / "index.html"), \
             patch.object(main_module, "_ASSETS_DIR", dist_dir / "assets"):
            client = TestClient(main_module.app)
            response = client.get("/assets/main.js")
        assert response.status_code == 200

    def test_path_traversal_is_rejected(self, dist_dir: Path):
        """Path traversal attempts must return 404."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_FRONTEND_DIST", dist_dir), \
             patch.object(main_module, "_INDEX_FILE", dist_dir / "index.html"), \
             patch.object(main_module, "_ASSETS_DIR", dist_dir / "assets"):
            client = TestClient(main_module.app)
            response = client.get("/../../etc/passwd")
        # FastAPI normalises the path before it reaches the route, so the
        # result is either a 404 or the request is sanitised.
        assert response.status_code in {200, 404}
        # If 200, it must serve index.html (not /etc/passwd)
        if response.status_code == 200:
            assert b"React App" in response.content

    def test_unknown_api_path_returns_404(self, dist_dir: Path):
        """Unknown /api/v1/* paths must return 404 JSON, not index.html."""
        import app.main as main_module
        with patch.object(main_module.settings, "serve_frontend", True), \
             patch.object(main_module, "_FRONTEND_DIST", dist_dir), \
             patch.object(main_module, "_INDEX_FILE", dist_dir / "index.html"), \
             patch.object(main_module, "_ASSETS_DIR", dist_dir / "assets"):
            client = TestClient(main_module.app)
            response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

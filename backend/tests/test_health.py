"""Tests for the health check endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_200():
    """The /api/v1/health endpoint should return HTTP 200."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_check_returns_healthy_status():
    """The health endpoint should report 'healthy' status."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "healthy"


def test_health_check_includes_service_name():
    """The health response should include the application name."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert "service" in data
    assert data["service"] == "AI CareerPilot"


def test_root_returns_docs_link():
    """The root endpoint should point to the API documentation."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["docs"] == "/docs"

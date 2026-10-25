"""Health check router.

Provides a simple endpoint to verify the backend is running.
Used by Docker health checks, load balancers, and manual verification.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return service status. No authentication required."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "0.1.0",
    }

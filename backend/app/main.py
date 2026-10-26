"""FastAPI application entry point for AI CareerPilot.

Creates the app, configures CORS, and registers all routers under the
/api/v1 prefix.

Frontend serving:
  Set SERVE_FRONTEND=true (e.g. in production Docker / Render) to have
  FastAPI serve the compiled React SPA.  When false (the default) the
  root endpoint returns a JSON info response so the test suite and local
  backend development continue to work unchanged.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.llm import get_llm_provider
from app.routers import (
    auth,
    health,
    interview_sessions,
    job_applications,
    job_descriptions,
    matches,
    resumes,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Intelligent Career & Job Application Platform — Backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — origins are configured via CORS_ORIGINS in .env (or environment).
# Default: localhost:5173 for local development.
# In production, set CORS_ORIGINS to the actual frontend URL(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers under the /api/v1 prefix
app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(resumes.router, prefix=settings.api_v1_prefix)
app.include_router(job_descriptions.router, prefix=settings.api_v1_prefix)
app.include_router(matches.router, prefix=settings.api_v1_prefix)
app.include_router(interview_sessions.router, prefix=settings.api_v1_prefix)
app.include_router(job_applications.router, prefix=settings.api_v1_prefix)


@app.get(f"{settings.api_v1_prefix}/features")
async def features():
    """Report availability of optional AI features without exposing secrets."""
    provider = get_llm_provider()
    return {
        "ai_powered": provider is not None and provider.is_available,
        "ai_features": {
            "resume_analysis": provider is not None,
            "enhanced_recommendations": provider is not None,
            "enhanced_feedback": provider is not None,
        },
    }


# ---------------------------------------------------------------------------
# Root endpoint — behaviour depends on SERVE_FRONTEND
# ---------------------------------------------------------------------------

# Resolve the frontend build directory relative to this file's location.
# File layout:
#   backend/app/main.py       → this file
#   backend/app/../..         → project root
#   <project_root>/frontend/dist/  → Vite build output
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_INDEX_FILE = _FRONTEND_DIST / "index.html"
_ASSETS_DIR = _FRONTEND_DIST / "assets"

# Mount the /assets route only when frontend serving is enabled AND the
# assets directory exists.  Conditional at startup so the server does not
# raise if dist/ is absent during development.
if settings.serve_frontend and _ASSETS_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_ASSETS_DIR)),
        name="frontend-assets",
    )
    logger.info("Frontend assets mounted from %s", _ASSETS_DIR)


@app.get("/")
async def root():
    """Root endpoint.

    - SERVE_FRONTEND=false (default, development/tests):
        Returns a JSON response with links to the API docs.  This is what
        the test suite asserts.

    - SERVE_FRONTEND=true (production):
        Returns the React index.html if the build is present, or a JSON
        fallback if it is missing (so the container starts cleanly even if
        the frontend build step was skipped).
    """
    if not settings.serve_frontend:
        # Default API info — matches the test expectation.
        return {
            "message": "AI CareerPilot API",
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    # Production mode — serve the React application.
    if _INDEX_FILE.is_file():
        return FileResponse(_INDEX_FILE)

    # Frontend build is missing.  Return a clear API fallback rather than
    # crashing or returning an empty response.
    logger.warning(
        "SERVE_FRONTEND=true but frontend build not found at %s", _FRONTEND_DIST
    )
    return {
        "message": "AI CareerPilot API",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
        "warning": "Frontend build not found. Run 'npm run build' inside frontend/.",
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_routes(full_path: str):
    """Serve static files or the React SPA entry point for client-side routes.

    Only active when SERVE_FRONTEND=true and the frontend build exists.

    Rules (applied in order):
    1. Requests that start with the API prefix → 404 JSON (not index.html).
    2. FastAPI built-in documentation paths → 404 JSON (FastAPI handles them
       via its own routes registered before this catch-all).
    3. Frontend build missing → 404 JSON.
    4. Path traversal attempt → 404 JSON.
    5. An existing file inside dist/ → serve that file directly.
    6. Anything else (a React Router path like /register) → serve index.html.
    """
    if not settings.serve_frontend:
        raise HTTPException(status_code=404, detail="Not found")

    api_prefix = settings.api_v1_prefix.strip("/")
    if full_path == api_prefix or full_path.startswith(api_prefix + "/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    if full_path in {"docs", "redoc", "openapi.json"}:
        # These are handled by FastAPI's own routes; this catch-all should
        # never be reached for them, but guard defensively.
        raise HTTPException(status_code=404, detail="Not found")

    if not _INDEX_FILE.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    # Prevent path traversal — resolve and verify it stays inside dist/.
    resolved_dist = _FRONTEND_DIST.resolve()
    requested_file = (_FRONTEND_DIST / full_path).resolve()
    try:
        requested_file.relative_to(resolved_dist)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found") from None

    if requested_file.is_file():
        return FileResponse(requested_file)

    # React Router handles client-side paths like /register and /login.
    return FileResponse(_INDEX_FILE)

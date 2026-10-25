"""FastAPI application entry point.

Creates the app, configures CORS, and registers all routers
under the /api/v1 prefix.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.llm import get_llm_provider
from app.routers import auth, health, interview_sessions, job_applications, job_descriptions, matches, resumes

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


@app.get("/")
async def root():
    """Root redirect info — points users to the API docs."""
    return {
        "message": "AI CareerPilot API",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }


@app.get(f"{settings.api_v1_prefix}/features")
async def features():
    """Return which optional features are available.

    This endpoint is public (no auth required) so the frontend can
    show honest labels about whether AI is powered by an LLM or
    deterministic heuristics. No secrets are exposed.
    """
    provider = get_llm_provider()
    return {
        "ai_powered": provider is not None and provider.is_available,
        "ai_features": {
            "resume_analysis": provider is not None,
            "enhanced_recommendations": provider is not None,
            "enhanced_feedback": provider is not None,
        },
    }

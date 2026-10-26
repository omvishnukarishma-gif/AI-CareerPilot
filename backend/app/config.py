"""Application configuration loaded from environment variables.

Uses pydantic-settings to read values from a .env file or environment.
This keeps secrets (like API keys and DB passwords) out of the code.
"""

import logging
from pathlib import Path
from typing import Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Backend directory: two levels up from this file (backend/app/config.py -> backend/)
_BACKEND_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Central configuration. Values are read from .env or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "AI CareerPilot"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # CORS — comma-separated string in env, parsed into a list.
    # Example: CORS_ORIGINS="http://localhost:5173,https://app.example.com"
    cors_origins: Union[list[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Database — uses psycopg3 (installed as `psycopg[binary]`).
    # The `+psycopg` suffix tells SQLAlchemy to use the psycopg3 driver
    # instead of the older psycopg2.
    database_url: str = "postgresql+psycopg://careerpilot:careerpilot_dev@localhost:5432/careerpilot_dev"

    # AI / LLM (used in Phase 2+)
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"

    # Frontend serving
    # Set SERVE_FRONTEND=true in production (Docker / Render) to serve the
    # compiled React build from FastAPI.  Leave it false (the default) for
    # local development and tests so `/` returns the JSON API info response
    # that the test suite expects.
    serve_frontend: bool = False

    # File uploads
    # upload_dir is relative to the working directory (backend/).
    # In production this should point to a persistent volume mount.
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 5

    # Security / JWT
    # In production, set SECRET_KEY to a strong random string (e.g. 32+ chars).
    # Generate one with:  python -c "import secrets; print(secrets.token_hex(32))"
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        """Accept either a list or a comma-separated string from env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return list(v)  # type: ignore[arg-type]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, v: object) -> object:
        """Normalise the database URL to use the psycopg3 SQLAlchemy dialect.

        Render (and many other providers) set DATABASE_URL with a bare
        ``postgresql://`` or ``postgres://`` scheme.  SQLAlchemy 2 requires
        ``postgresql+psycopg://`` to use the psycopg3 driver.  This validator
        rewrites the scheme automatically so operators do not need to edit
        the value injected by their platform.

        The URL value is never logged — only the scheme prefix is inspected.
        """
        if not isinstance(v, str):
            return v
        # Map legacy / provider-supplied schemes to psycopg3 scheme
        replacements = {
            "postgres://": "postgresql+psycopg://",
            "postgresql://": "postgresql+psycopg://",
        }
        for old, new in replacements.items():
            if v.startswith(old):
                return new + v[len(old):]
        return v

    @model_validator(mode="after")
    def resolve_upload_dir(self) -> "Settings":
        """Convert a relative upload_dir to an absolute path.

        The path is resolved relative to the backend/ directory so it is
        stable regardless of the working directory the server is started from.
        """
        path = Path(self.upload_dir)
        if not path.is_absolute():
            self.upload_dir = str(_BACKEND_DIR / path)
        return self

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        """Enforce a strong SECRET_KEY in production; warn in development.

        - If SERVE_FRONTEND=true (production / Docker / Render) and the dev
          default key is still in use, startup is aborted with a clear error.
          This prevents deploying with a known-insecure signing secret.
        - In local development (SERVE_FRONTEND=false) the application starts
          but logs a prominent warning so the developer is reminded to rotate
          the key before going live.

        To generate a strong key:
            python -c "import secrets; print(secrets.token_hex(32))"
        """
        _DEV_DEFAULT = "dev-secret-key-change-in-production"
        if self.secret_key == _DEV_DEFAULT:
            if self.serve_frontend:
                # Production mode — refuse to start with an insecure key.
                raise ValueError(
                    "SECRET_KEY is set to the insecure development default. "
                    "Set SECRET_KEY to a strong random value before deploying. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            else:
                # Development mode — warn but allow startup.
                logger.warning(
                    "SECRET_KEY is set to the insecure development default. "
                    "Set SECRET_KEY to a strong random value before deploying to production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
        return self


# Single shared settings instance
settings = Settings()

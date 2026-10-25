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
    def warn_insecure_secret_key(self) -> "Settings":
        """Log a warning when the default development secret key is in use.

        Never raises — the application starts regardless.  Production operators
        MUST set SECRET_KEY to a strong random value.  To generate one:
            python -c "import secrets; print(secrets.token_hex(32))"
        """
        if self.secret_key == "dev-secret-key-change-in-production":
            logger.warning(
                "SECRET_KEY is set to the insecure development default. "
                "Set SECRET_KEY to a strong random value before deploying to production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self


# Single shared settings instance
settings = Settings()

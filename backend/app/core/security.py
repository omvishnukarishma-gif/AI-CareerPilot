"""Security utilities — password hashing and JWT token operations.

This module provides two core security primitives:
1. Password hashing using bcrypt (via passlib).
2. JWT token creation and verification (via python-jose).

Both are configured from environment variables (see app.config.settings).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# --- Password hashing ---

# bcrypt is the recommended password hashing algorithm.
# 'deprecated=auto' means passlib will use the latest bcrypt variant ($2b$).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    The resulting hash includes a random salt, so the same password
    produces a different hash each time.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Returns True if the password matches, False otherwise.
    Uses constant-time comparison internally to prevent timing attacks.
    """
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT token operations ---

def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data:         The payload to encode (e.g. {"sub": "user@example.com"}).
        expires_delta: Custom expiration time. Defaults to settings value.

    Returns:
        A signed JWT string.
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT access token.

    Returns the token payload if valid, or None if the token is
    expired, malformed, or has an invalid signature.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None

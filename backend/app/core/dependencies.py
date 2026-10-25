"""FastAPI authentication dependencies.

These are reusable functions that FastAPI injects into route handlers
via `Depends(...)`.  They handle the work of extracting the JWT token
from the request, validating it, and looking up the current user.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

# OAuth2PasswordBearer tells FastAPI to look for a Bearer token in the
# Authorization header.  The tokenUrl is the path to the login endpoint —
# it's used by the Swagger UI "Authorize" button and does NOT hardcode
# any security behavior.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate the JWT token and return the authenticated User.

    Raises 401 if:
    - The token is missing (OAuth2PasswordBearer handles this).
    - The token is malformed or expired (decode_access_token returns None).
    - The subject (sub) is not in the payload.
    - The user doesn't exist or is inactive.

    Security note: The user is identified solely by the token payload.
    A client-supplied user ID is never accepted as proof of identity.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="The bearer token included in the request is invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # "sub" (subject) is a standard JWT claim — we store the user email in it.
    email: str | None = payload.get("sub")
    if email is None:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise credentials_exception

    return user

"""Authentication router — registration, login, and current-user endpoints.

All endpoints are mounted under /api/v1/auth (via main.py's prefix).

Flow:
    POST /auth/register  → create account, return safe user data
    POST /auth/login     → verify credentials, return JWT access token
    GET  /auth/me         → return the authenticated user's safe data
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Register a new user.

    - Normalizes email to lowercase before storing and checking uniqueness.
    - Hashes the password with bcrypt before storing.
    - Returns 201 with safe user data on success.
    - Returns 409 if the email is already registered.
    - Returns 422 if the input doesn't pass Pydantic validation.
    """
    email = payload.email.lower().strip()

    # Check for existing user with the same normalized email
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT access token.

    - Normalizes email to lowercase before lookup.
    - Returns the same error for 'user not found' and 'wrong password'
      so an attacker can't discover which emails are registered.
    - Returns 200 with the token on success.
    - Returns 401 for invalid credentials.
    """
    email = payload.email.lower().strip()

    user = db.query(User).filter(User.email == email).first()

    # Same error message for both cases to prevent user enumeration
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # "sub" (subject) is a standard JWT claim — we store the user's email.
    token = create_access_token(data={"sub": user.email})

    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's safe public information.

    Requires a valid Bearer token in the Authorization header.
    Returns 401 if the token is missing, invalid, or expired.
    """
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the authenticated user's profile.

    - full_name: update display name.
    - new_password: must be supplied together with current_password.
      Returns 400 if current_password is missing or incorrect.
    - Returns the updated user without exposing the password hash.
    """
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()

    if payload.new_password is not None:
        if not payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current_password is required to change the password.",
            )
        if not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )
        current_user.password_hash = hash_password(payload.new_password)

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)

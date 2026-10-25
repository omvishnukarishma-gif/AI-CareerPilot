"""Pydantic schemas for authentication endpoints.

These define the shape of data that comes in (requests) and goes out
(responses) from the auth API.  They also serve as validation: FastAPI
automatically rejects requests that don't match the schema.
"""

from pydantic import BaseModel, EmailStr, Field


# --- Request schemas ---


class UserRegister(BaseModel):
    """Registration request body.

    email:      Must be a valid email format (validated by email-validator).
    password:   Minimum 8 characters, maximum 128.
    full_name:  Non-empty display name, max 255 chars.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserLogin(BaseModel):
    """Login request body.

    We don't reveal whether an email exists or not — the login endpoint
    returns the same error for 'user not found' and 'wrong password'.
    """

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# --- Response schemas ---


class UserResponse(BaseModel):
    """Safe user representation returned by the API.

    NEVER includes the password hash or any sensitive field.
    This is the only shape in which user data leaves the server.
    """

    id: int
    email: str
    full_name: str
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT access token response returned after successful login."""

    access_token: str
    token_type: str = "bearer"


class UserUpdate(BaseModel):
    """Request body for PUT /auth/me — profile editing.

    All fields are optional so partial updates are supported.
    To change the password, both current_password and new_password must be supplied.
    Supplying new_password without current_password returns 400.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    current_password: str | None = Field(default=None, min_length=1, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

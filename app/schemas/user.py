"""Pydantic schemas for users and authentication."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    """Payload for registration."""

    password: str


class UserLogin(UserBase):
    """Payload for login."""

    password: str


class UserRead(UserBase):
    """User data returned to clients (never includes the password)."""

    id: int
    learning_goal: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT token response (used by the future mobile/API clients)."""

    access_token: str
    token_type: str = "bearer"

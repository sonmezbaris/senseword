"""Authentication service: password hashing, JWT tokens, and user lookup.

The web app authenticates with a signed session cookie that contains a JWT.
The same JWT scheme can be reused by the future mobile app via the
``Authorization: Bearer <token>`` header, so the auth logic lives here in one
reusable place rather than in the routers.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate

# ---------------------------------------------------------------------------
# Config (override via environment variables in production)
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days
SESSION_COOKIE_NAME = "access_token"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------
def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    """Return the user id from a token, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return int(user_id) if user_id is not None else None
    except (JWTError, ValueError):
        return None


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------
def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, payload: UserCreate) -> User:
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


# ---------------------------------------------------------------------------
# Onboarding (learning goal)
# ---------------------------------------------------------------------------
# Allowed learning goals, in display order. Keeping the canonical list here
# lets routers/templates share one source of truth and validate input.
LEARNING_GOALS = (
    "IELTS",
    "TOEFL",
    "YDS / YÖKDİL",
    "Business English",
    "Daily English",
    "Academic English",
)


def is_valid_goal(goal: str) -> bool:
    return goal in LEARNING_GOALS


def set_learning_goal(db: Session, user: User, goal: str) -> User:
    """Persist the user's chosen learning goal."""
    user.learning_goal = goal
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# FastAPI dependencies for protecting routes
# ---------------------------------------------------------------------------
def _extract_token(request: Request) -> str | None:
    """Read the JWT from the cookie (web) or Authorization header (mobile)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()
    return None


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Return the logged-in user or None (for pages that work either way)."""
    token = _extract_token(request)
    if not token:
        return None
    user_id = decode_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """Require an authenticated user; raise 401 otherwise."""
    user = get_current_user_optional(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user

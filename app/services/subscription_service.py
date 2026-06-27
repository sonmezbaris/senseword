"""Subscription and premium-access service.

Handles plan state, premium checks, and manual/provider activation. Payment
integrations (Stripe, Lemon Squeezy, Paddle) are stubbed with TODO markers so
they can be wired in later without changing routers.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import (
    PLAN_FOUNDING,
    PLAN_FREE,
    PLAN_PREMIUM,
    SUB_ACTIVE,
    SUB_CANCELED,
    SUB_EXPIRED,
    SUB_INACTIVE,
    SUB_TRIALING,
    User,
)

# Learning paths available on the Free plan (slug set). All others are Premium.
FREE_PATH_SLUGS = {"daily-english"}

# Premium-only exam / professional paths (for UI labels).
PREMIUM_PATH_GOALS = {
    "IELTS",
    "TOEFL",
    "YDS / YÖKDİL",
    "Business English",
    "Academic English",
}


def user_has_premium_access(user: User) -> bool:
    """Everything is free now — every feature is unlocked for all users.

    The paywall has been removed: words, learning paths, reviews, weak-word
    practice and exams are available to everyone without payment or limits.
    """
    return True


def get_user_plan_label(user: User) -> str:
    """Human-readable plan name for the dashboard (everyone is full-access)."""
    return "Full access"


def can_access_path(user: User, path_slug: str) -> bool:
    """All learning paths are free for everyone."""
    return True


def is_premium_path_slug(path_slug: str) -> bool:
    """No path is premium anymore."""
    return False


# ---------------------------------------------------------------------------
# Subscription lifecycle (manual for now; provider hooks later)
# ---------------------------------------------------------------------------
def activate_subscription(
    db: Session,
    user: User,
    plan: str,
    provider: str = "manual",
    *,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    period_end: datetime | None = None,
) -> User:
    """Activate or upgrade a user's subscription."""
    if plan not in {PLAN_PREMIUM, PLAN_FOUNDING}:
        raise ValueError(f"Cannot activate plan: {plan}")
    user.plan = plan
    user.subscription_status = SUB_ACTIVE
    user.subscription_provider = provider
    user.subscription_customer_id = customer_id
    user.subscription_id = subscription_id
    user.subscription_current_period_end = period_end
    db.commit()
    db.refresh(user)
    return user


def cancel_subscription(db: Session, user: User) -> User:
    """Mark subscription canceled (access may continue until period end)."""
    user.subscription_status = SUB_CANCELED
    db.commit()
    db.refresh(user)
    return user


def expire_subscription(db: Session, user: User) -> User:
    """Downgrade to Free after expiry."""
    user.plan = PLAN_FREE
    user.subscription_status = SUB_EXPIRED
    db.commit()
    db.refresh(user)
    return user


# TODO: connect Stripe Checkout here
# def create_stripe_checkout_session(user: User) -> str: ...

# TODO: add Lemon Squeezy webhook here
# def handle_lemonsqueezy_webhook(payload: dict) -> None: ...

# TODO: add Paddle webhook here
# def handle_paddle_webhook(payload: dict) -> None: ...

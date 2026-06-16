#!/usr/bin/env python3
"""Manually activate Premium or Founding Member for a user (MVP admin tool).

Usage (from the ``senseword/`` directory):

    python scripts/activate_premium.py user@example.com premium
    python scripts/activate_premium.py user@example.com founding

Sets plan, subscription_status=active, subscription_provider=manual.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.user import PLAN_FOUNDING, PLAN_PREMIUM  # noqa: E402
from app.services import auth_service, subscription_service  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: python scripts/activate_premium.py <email> <premium|founding>",
            file=sys.stderr,
        )
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    plan_arg = sys.argv[2].strip().lower()
    plan_map = {"premium": PLAN_PREMIUM, "founding": PLAN_FOUNDING}
    if plan_arg not in plan_map:
        print("Plan must be 'premium' or 'founding'", file=sys.stderr)
        sys.exit(1)
    plan = plan_map[plan_arg]

    init_db()
    db = SessionLocal()
    try:
        user = auth_service.get_user_by_email(db, email)
        if not user:
            print(f"User not found: {email}", file=sys.stderr)
            sys.exit(1)
        subscription_service.activate_subscription(db, user, plan, provider="manual")
        print(
            f"Activated {plan} for {email} "
            f"(status={user.subscription_status}, provider=manual)"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

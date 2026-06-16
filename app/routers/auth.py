"""Authentication routes: register, login, logout.

These routes serve HTML forms for the web app and set a JWT session cookie.
A JSON API counterpart can be added later for the mobile app reusing the same
``auth_service`` functions.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import templates
from app.schemas.user import UserCreate
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None})


@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if auth_service.get_user_by_email(db, email):
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "An account with that email already exists."},
            status_code=400,
        )

    user = auth_service.create_user(db, UserCreate(email=email, password=password))
    token = auth_service.create_access_token(user.id)

    # New users always start with onboarding (no learning goal yet).
    response = RedirectResponse(url="/onboarding", status_code=303)
    response.set_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password."},
            status_code=401,
        )

    token = auth_service.create_access_token(user.id)
    # After signing in the user always lands on the goal-selection page
    # (IELTS / Business / ...), pre-selecting their current goal if any. From
    # there they go straight into the learning stage for that goal.
    response = RedirectResponse(url="/onboarding", status_code=303)
    response.set_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(auth_service.SESSION_COOKIE_NAME)
    return response

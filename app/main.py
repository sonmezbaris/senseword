"""SenseWord — FastAPI application entry point.

A multisensory English-vocabulary learning MVP. See README.md for setup.

Run locally from the ``senseword/`` directory:

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Or with auto-reload during development:

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Or use the helper script (same host/port, reload enabled):

    python run.py
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import DATABASE_URL, SessionLocal, get_db, init_db, safe_database_url
from app.models.user import User
from app.routers import (
    api,
    auth,
    dashboard,
    learning,
    onboarding,
    paths,
    review,
    study,
    subscription,
    templates,
    vocabulary,
    weak_words,
)
from app.services import learning_path_service, seed_service
from app.services.auth_service import get_current_user_optional

BASE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger("senseword")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log which database we're actually using (credentials masked). This makes
    # it obvious in the Replit logs whether the deployment points at the same
    # database as local development.
    logging.basicConfig(level=logging.INFO)
    logger.info("SenseWord starting — using database: %s", safe_database_url())
    if DATABASE_URL.startswith("sqlite"):
        # The path after "sqlite:///" is the actual file on disk.
        logger.info("SQLite file path: %s", DATABASE_URL.replace("sqlite:///", "", 1))

    # Create tables on startup (MVP convenience; use Alembic for real schema changes).
    init_db()
    # Load the curated vocabulary catalog if the table is empty, then build
    # the learning paths from it (both steps are idempotent). This is what lets
    # a fresh Replit deployment populate its own database automatically.
    db = SessionLocal()
    try:
        seed_result = seed_service.seed_if_empty(db)
        path_result = learning_path_service.seed_learning_paths(db)
        logger.info(
            "Catalog seed: %s | Learning paths: %s", seed_result, path_result
        )
    finally:
        db.close()
    yield


app = FastAPI(title="SenseWord", lifespan=lifespan)

# Static files (CSS / JS).
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

# Register routers.
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(dashboard.router)
app.include_router(vocabulary.router)
app.include_router(learning.router)
app.include_router(review.router)
app.include_router(study.router)
app.include_router(paths.router)
app.include_router(weak_words.router)
app.include_router(subscription.router)
app.include_router(api.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    """Landing page. Logged-in users are sent straight to the dashboard."""
    user: User | None = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "index.html", {"user": None})


@app.get("/health")
def health():
    """Simple health check endpoint."""
    return {"status": "ok"}

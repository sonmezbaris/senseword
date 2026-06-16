"""Learning path routes: browse available paths and view a path's detail."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import learning_path_service, subscription_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/paths", tags=["learning-paths"])


@router.get("", response_class=HTMLResponse)
def browse_paths(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all active learning paths with their word counts."""
    paths = learning_path_service.list_active_paths(db)
    counts = learning_path_service.word_counts_for_paths(db)
    premium = subscription_service.user_has_premium_access(user)
    rows = []
    for p in paths:
        locked = not subscription_service.can_access_path(user, p.slug)
        rows.append(
            {
                "path": p,
                "word_count": counts.get(p.id, 0),
                "locked": locked,
            }
        )
    return templates.TemplateResponse(
        request,
        "paths_list.html",
        {"user": user, "rows": rows, "premium": premium},
    )


@router.get("/{slug}", response_class=HTMLResponse)
def path_detail(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Show one path: name, description, level, word count, and its words."""
    path = learning_path_service.get_path_by_slug(db, slug)
    if not path or not path.is_active:
        raise HTTPException(status_code=404, detail="Learning path not found")

    if not subscription_service.can_access_path(user, path.slug):
        return RedirectResponse(url="/upgrade", status_code=303)

    words = learning_path_service.list_path_words(db, path.id)
    word_count = len(words)

    # Resume support: where the user left off (clamped to a valid word).
    progress = learning_path_service.get_progress(db, user.id, path.id)
    resume_index = 0
    if progress and word_count:
        resume_index = max(0, min(progress.current_index, word_count - 1))

    return templates.TemplateResponse(
        request,
        "path_detail.html",
        {
            "user": user,
            "path": path,
            "words": words,
            "word_count": word_count,
            "progress": progress,
            "resume_index": resume_index,
            "studied": learning_path_service.count_studied_in_path(
                db, user.id, path.id
            ),
        },
    )

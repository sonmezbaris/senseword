"""Study routes: browse the catalog by level and study words one at a time.

Two screens:
  * ``GET /study``               — browse list: filter by level, choose how many
                                    words to show at once (100 / 500 / 1000),
                                    paginate, and jump straight to any word.
  * ``GET /study/card/{pos}``    — the progressive multisensory learning card
                                    for a single word, with single- and
                                    multi-step navigation (±1 / ±10 / ±100).
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import (
    catalog_service,
    learning_path_service,
    mission_service,
    progress_service,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/study", tags=["study"])

# User voice recordings are written here and served via the /static mount.
RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "static" / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# How many words the browse list can show per page.
ALLOWED_PAGE_SIZES = (100, 500, 1000)
# Multi-step jump sizes offered on the study card.
JUMP_STEPS = (10, 100)


def _clean_level(level: str | None) -> str | None:
    """Return a valid level filter, or None for 'all'."""
    if level and level in catalog_service.LEVELS:
        return level
    return None


# ---------------------------------------------------------------------------
# Browse list
# ---------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def study_browse(
    request: Request,
    level: str = "all",
    page: int = 1,
    size: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List words for a level, paginated, with multi-jump links to each word."""
    level_filter = _clean_level(level)
    if size not in ALLOWED_PAGE_SIZES:
        size = ALLOWED_PAGE_SIZES[0]

    total = catalog_service.count_words(db, level_filter)
    total_pages = max(1, math.ceil(total / size)) if total else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * size

    words = catalog_service.list_words(db, limit=size, offset=offset, level=level_filter)
    answered_ids = catalog_service.answered_word_ids(db, user.id)

    # Position of each row within the (level-filtered) catalog, so the card
    # screen can navigate using the same filter.
    start_position = offset
    rows = [
        {"word": w, "position": start_position + i, "answered": w.id in answered_ids}
        for i, w in enumerate(words)
    ]

    return templates.TemplateResponse(
        request,
        "study_list.html",
        {
            "user": user,
            "rows": rows,
            "level": level if (level == "all" or level_filter) else "all",
            "level_counts": catalog_service.level_counts(db),
            "levels": catalog_service.LEVELS,
            "page": page,
            "size": size,
            "page_sizes": ALLOWED_PAGE_SIZES,
            "total": total,
            "total_pages": total_pages,
            "answered_total": catalog_service.count_answered(db, user.id),
        },
    )


# ---------------------------------------------------------------------------
# Single-word study card
# ---------------------------------------------------------------------------
@router.get("/card/{position}", response_class=HTMLResponse)
def study_card(
    position: int,
    request: Request,
    level: str = "all",
    size: int = 100,
    path: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Study one word at a time.

    Two modes share this screen:
      * Catalog mode (default): navigate the catalog filtered by ``level``.
      * Path mode (``?path=<slug>``): navigate the words of a learning path,
        in path order. Navigation links and the "back" link stay in the path.
    """
    if path:
        return _render_path_card(request, db, user, position, path)
    return _render_catalog_card(request, db, user, position, level, size)


def _build_nav(position: int, total: int) -> dict:
    """Prev/next single-step and multi-step (±10, ±100) targets, clamped."""

    def jump(delta: int) -> int | None:
        target = position + delta
        if target < 0 or target > total - 1 or target == position:
            return None
        return target

    return {
        "prev_1": jump(-1),
        "next_1": jump(1),
        "jumps_back": [(step, jump(-step)) for step in JUMP_STEPS],
        "jumps_fwd": [(step, jump(step)) for step in JUMP_STEPS],
    }


def _render_catalog_card(
    request: Request, db: Session, user: User, position: int, level: str, size: int
) -> HTMLResponse:
    level_filter = _clean_level(level)
    if size not in ALLOWED_PAGE_SIZES:
        size = ALLOWED_PAGE_SIZES[0]

    total = catalog_service.count_words(db, level_filter)
    if total == 0:
        return templates.TemplateResponse(
            request, "study.html", {"user": user, "word": None, "total": 0}
        )

    position = max(0, min(position, total - 1))
    word = catalog_service.get_word_at_position(db, position, level_filter)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    display_level = level if (level == "all" or level_filter) else "all"
    list_page = position // size + 1
    return templates.TemplateResponse(
        request,
        "study.html",
        {
            "user": user,
            "word": word,
            "answer": catalog_service.get_answer(db, user.id, word.id),
            "position": position,
            "total": total,
            "answered": catalog_service.count_answered(db, user.id),
            "nav": _build_nav(position, total),
            # Query string carried by all in-card navigation links.
            "nav_qs": f"level={display_level}&size={size}",
            "back_url": f"/study?level={display_level}&size={size}&page={list_page}",
            "back_label": "Word list",
            "context_label": None,
        },
    )


def _render_path_card(
    request: Request, db: Session, user: User, position: int, slug: str
) -> HTMLResponse:
    lp = learning_path_service.get_path_by_slug(db, slug)
    if not lp or not lp.is_active:
        raise HTTPException(status_code=404, detail="Learning path not found")

    total = learning_path_service.count_path_words(db, lp.id)
    if total == 0:
        return templates.TemplateResponse(
            request, "study.html", {"user": user, "word": None, "total": 0}
        )

    position = max(0, min(position, total - 1))
    word = learning_path_service.get_path_word_at_position(db, lp.id, position)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    # Remember where the user is so "Start study" can resume later.
    learning_path_service.update_progress_position(db, user.id, lp.id, position)

    is_last = position >= total - 1
    return templates.TemplateResponse(
        request,
        "study.html",
        {
            "user": user,
            "word": word,
            "answer": catalog_service.get_answer(db, user.id, word.id),
            "position": position,
            "total": total,
            "answered": catalog_service.count_answered(db, user.id),
            "nav": _build_nav(position, total),
            "nav_qs": f"path={lp.slug}",
            "back_url": f"/paths/{lp.slug}",
            "back_label": "Back to path",
            "context_label": lp.name,
            # Path-study extras (the catalog mode leaves these unset).
            "studied_in_path": learning_path_service.count_studied_in_path(
                db, user.id, lp.id
            ),
            # On the last word, "Next" becomes "Finish" → completion page.
            "finish_url": f"/study/path/{lp.slug}/complete" if is_last else None,
        },
    )


@router.get("/review", response_class=HTMLResponse)
def study_review(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Spaced-repetition review: serve the next word due for review.

    Reuses the study card. After the learner completes (saves) the word, its
    ``next_review_at`` moves into the future, so reloading this page serves the
    next due word. When nothing is due, a short "all caught up" state shows.
    """
    due_total = progress_service.count_due_reviews(db, user.id)
    due = progress_service.get_next_due_word(db, user.id)
    if not due:
        return templates.TemplateResponse(
            request,
            "study.html",
            {"user": user, "word": None, "review_done": True},
        )

    word = catalog_service.get_word_by_id(db, due.word_id)
    if not word:
        # Orphaned progress row (word removed): skip it gracefully.
        return templates.TemplateResponse(
            request,
            "study.html",
            {"user": user, "word": None, "review_done": True},
        )

    return templates.TemplateResponse(
        request,
        "study.html",
        {
            "user": user,
            "word": word,
            "answer": catalog_service.get_answer(db, user.id, word.id),
            "position": 0,
            "total": due_total,
            "answered": catalog_service.count_answered(db, user.id),
            # No position-based stepping in review mode.
            "nav": _build_nav(0, 1),
            "nav_qs": "",
            "back_url": "/dashboard",
            "back_label": "Dashboard",
            "context_label": "Review due",
            # Drives the "Next due →" button (reloads to the next due word).
            "review_next_url": "/study/review",
        },
    )


def _render_single_word(
    request: Request,
    db: Session,
    user: User,
    word,
    *,
    back_url: str,
    back_label: str,
    context_label: str,
    next_url: str | None = None,
) -> HTMLResponse:
    """Render the study card for one standalone word (no position stepping)."""
    return templates.TemplateResponse(
        request,
        "study.html",
        {
            "user": user,
            "word": word,
            "answer": catalog_service.get_answer(db, user.id, word.id),
            "position": 0,
            "total": 1,
            "answered": catalog_service.count_answered(db, user.id),
            "nav": _build_nav(0, 1),
            "nav_qs": "",
            "back_url": back_url,
            "back_label": back_label,
            "context_label": context_label,
            # When set, the card shows a single "Next →" style button.
            "review_next_url": next_url,
        },
    )


@router.get("/word/{word_id}", response_class=HTMLResponse)
def study_single_word(
    word_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Study one specific catalog word (used by the Weak Words "Study" button)."""
    word = catalog_service.get_word_by_id(db, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return _render_single_word(
        request,
        db,
        user,
        word,
        back_url="/weak-words",
        back_label="Weak words",
        context_label="Practice word",
    )


@router.get("/weak", response_class=HTMLResponse)
def study_weak(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Review weak words one at a time, weakest first (reuses the study card)."""
    weak = progress_service.get_next_weak_word(db, user.id)
    if not weak:
        return templates.TemplateResponse(
            request, "study.html", {"user": user, "word": None, "weak_done": True}
        )

    word = catalog_service.get_word_by_id(db, weak.word_id)
    if not word:
        return templates.TemplateResponse(
            request, "study.html", {"user": user, "word": None, "weak_done": True}
        )

    return _render_single_word(
        request,
        db,
        user,
        word,
        back_url="/weak-words",
        back_label="Weak words",
        context_label="Weak words",
        # Reloads to serve the next weak word after this one is completed.
        next_url="/study/weak",
    )


def _normalize_answer(text: str) -> str:
    """Case/whitespace-insensitive normalization for answer comparison."""
    return " ".join(text.strip().lower().split())


def _pick_recall_word(db: Session, user_id: int):
    """Next word for recall practice: due words first, then weak words."""
    progress = progress_service.get_next_due_word(db, user_id)
    if progress is None:
        progress = progress_service.get_next_weak_word(db, user_id)
    if progress is None:
        return None
    return catalog_service.get_word_by_id(db, progress.word_id)


@router.get("/recall", response_class=HTMLResponse)
def recall_question(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Turkish → English reverse review: show the meaning, ask for the word."""
    word = _pick_recall_word(db, user.id)
    if not word:
        return templates.TemplateResponse(
            request, "recall.html", {"user": user, "word": None, "result": None}
        )
    return templates.TemplateResponse(
        request,
        "recall.html",
        {"user": user, "word": word, "result": None},
    )


@router.post("/recall", response_class=HTMLResponse)
def recall_submit(
    request: Request,
    catalog_word_id: int = Form(...),
    answer: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Grade a recall answer (case/space-insensitive) and update progress."""
    word = catalog_service.get_word_by_id(db, catalog_word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    is_correct = _normalize_answer(answer) == _normalize_answer(word.word)

    # Update spaced-repetition progress from the result.
    progress_service.mark_word_seen(db, user.id, catalog_word_id)
    progress = progress_service.update_memory_strength(
        db, user.id, catalog_word_id, "correct" if is_correct else "wrong"
    )
    # Recall practice counts as a review toward the daily mission.
    mission_service.record_review_word(db, user.id)

    return templates.TemplateResponse(
        request,
        "recall.html",
        {
            "user": user,
            "word": word,
            "result": {
                "is_correct": is_correct,
                "user_answer": answer.strip(),
                "correct_word": word.word,
                "memory_strength": progress.memory_strength,
            },
        },
    )


@router.get("/listening", response_class=HTMLResponse)
def listening_question(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Listening review: the user hears the word (TTS) and types what they heard."""
    word = _pick_recall_word(db, user.id)
    if not word:
        return templates.TemplateResponse(
            request, "listening.html", {"user": user, "word": None, "result": None}
        )
    return templates.TemplateResponse(
        request,
        "listening.html",
        {"user": user, "word": word, "result": None},
    )


@router.post("/listening", response_class=HTMLResponse)
def listening_submit(
    request: Request,
    catalog_word_id: int = Form(...),
    answer: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Grade a listening answer (case/space-insensitive) and update progress."""
    word = catalog_service.get_word_by_id(db, catalog_word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    is_correct = _normalize_answer(answer) == _normalize_answer(word.word)

    progress_service.mark_word_seen(db, user.id, catalog_word_id)
    progress = progress_service.update_memory_strength(
        db, user.id, catalog_word_id, "correct" if is_correct else "wrong"
    )
    mission_service.record_review_word(db, user.id)

    return templates.TemplateResponse(
        request,
        "listening.html",
        {
            "user": user,
            "word": word,
            "result": {
                "is_correct": is_correct,
                "user_answer": answer.strip(),
                "correct_word": word.word,
                "memory_strength": progress.memory_strength,
            },
        },
    )


@router.get("/path/{slug}/complete", response_class=HTMLResponse)
def path_complete(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Completion screen shown after finishing the last word in a path."""
    lp = learning_path_service.get_path_by_slug(db, slug)
    if not lp or not lp.is_active:
        raise HTTPException(status_code=404, detail="Learning path not found")

    total = learning_path_service.count_path_words(db, lp.id)
    learning_path_service.mark_path_completed(db, user.id, lp.id)

    studied = learning_path_service.count_studied_in_path(db, user.id, lp.id)
    weak_position = learning_path_service.first_unstudied_position(db, user.id, lp.id)
    weak_count = max(0, total - studied)

    return templates.TemplateResponse(
        request,
        "study_complete.html",
        {
            "user": user,
            "path": lp,
            "total": total,
            "studied": studied,
            "weak_count": weak_count,
            # Where the "review weak words" button jumps to (first skipped word,
            # or the start of the path if every word was studied).
            "weak_position": weak_position if weak_position is not None else 0,
        },
    )


@router.post("/answer")
async def save_answer(
    catalog_word_id: int = Form(...),
    user_sentence: str = Form(""),
    audio: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save the learner's sentence and (optionally) their voice recording.

    Called via fetch() from the study screen. Returns JSON so the page can
    confirm the save without a full reload.
    """
    word = catalog_service.get_word_by_id(db, catalog_word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    # Is this the first time the user studies this word? Checked before we
    # mark it seen, so we can credit the right daily-mission goal.
    prior = progress_service.get_or_create_progress(db, user.id, catalog_word_id)
    is_new_word = prior.times_seen == 0

    recording_url = None
    if audio is not None and audio.filename:
        recording_url = await _store_recording(user.id, catalog_word_id, audio)

    answer = catalog_service.save_answer(
        db,
        user.id,
        catalog_word_id,
        user_sentence=user_sentence.strip() or None,
        recording_url=recording_url,
    )

    # Completing a word (saving an answer) counts as a successful exposure:
    # record that it was seen and strengthen the user's memory of it.
    progress_service.mark_word_seen(db, user.id, catalog_word_id)
    progress_service.update_memory_strength(db, user.id, catalog_word_id, "correct")

    # Daily mission: first study of a word counts as a new word, otherwise a
    # review; a recording counts as a voice practice.
    if is_new_word:
        mission_service.record_new_word(db, user.id)
    else:
        mission_service.record_review_word(db, user.id)
    if recording_url:
        mission_service.record_voice_practice(db, user.id)

    return JSONResponse(
        {
            "ok": True,
            "answer_id": answer.id,
            "user_sentence": answer.user_sentence,
            "recording_url": answer.recording_url,
        }
    )


async def _store_recording(
    user_id: int, word_id: int, audio: UploadFile
) -> str:
    """Persist an uploaded audio blob and return its public /static URL."""
    # Guess an extension from the content type (browsers usually send webm).
    ext = ".webm"
    if audio.content_type and "ogg" in audio.content_type:
        ext = ".ogg"
    elif audio.content_type and "mp4" in audio.content_type:
        ext = ".mp4"
    elif audio.content_type and "wav" in audio.content_type:
        ext = ".wav"

    filename = f"u{user_id}_w{word_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest = RECORDINGS_DIR / filename
    content = await audio.read()
    dest.write_bytes(content)
    return f"/static/recordings/{filename}"

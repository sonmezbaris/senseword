"""Exam service — generate multiple-choice cloze (fill-in-the-blank) tests.

Bridges the standalone ``scripts/exam_generator.py`` with the web app. The word
pool is built once from the catalog (works for SQLite *and* Postgres because it
reads through SQLAlchemy, not raw sqlite3) and cached in memory for fast,
repeated exam generation.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.catalog import CatalogWord

# ---------------------------------------------------------------------------
# Load the generator module by file path (scripts/ is not an importable package).
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_GEN_PATH = _PROJECT_ROOT / "scripts" / "exam_generator.py"

_spec = importlib.util.spec_from_file_location("exam_generator", _GEN_PATH)
_eg = importlib.util.module_from_spec(_spec)
# Register before executing so dataclasses can resolve the module's annotations.
sys.modules[_spec.name] = _eg
_spec.loader.exec_module(_eg)  # type: ignore[union-attr]

# Exam types in display order.
EXAM_ORDER = ["IELTS", "TOEFL", "YDS", "E-YDS"]

_pool_lock = threading.Lock()
_pool = None  # cached exam_generator.WordPool


def _build_pool(db: Session):
    """Build a WordPool from every catalog word (cached after first call)."""
    rows = db.query(
        CatalogWord.word,
        CatalogWord.turkish_translation,
        CatalogWord.pronunciation,
        CatalogWord.example_sentence,
        CatalogWord.example_sentence_tr,
        CatalogWord.level,
        CatalogWord.word_type,
    ).all()
    words = [
        _eg.Word(
            word=r[0],
            turkish=r[1] or "",
            pronunciation=r[2] or "",
            example_sentence=r[3] or "",
            example_sentence_tr=r[4] or "",
            level=r[5] or "intermediate",
            word_type=r[6],
        )
        for r in rows
    ]
    return _eg.WordPool(words)


def get_pool(db: Session):
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _build_pool(db)
    return _pool


def reset_pool() -> None:
    """Drop the cached pool (e.g. after the catalog is reseeded)."""
    global _pool
    with _pool_lock:
        _pool = None


def list_exam_types() -> list[dict]:
    """Metadata for the exam picker page."""
    out = []
    for key in EXAM_ORDER:
        cfg = _eg.EXAM_CONFIGS[key]
        out.append(
            {
                "key": key,
                "slug": key.lower(),
                "display_name": cfg.display_name,
                "total_minutes": cfg.total_minutes,
                "num_options": cfg.num_options,
                "total_questions": cfg.total_questions,
                "delivery": cfg.delivery,
                "rules": cfg.rules,
            }
        )
    return out


def resolve_exam_type(name: str) -> str:
    return _eg.resolve_exam_type(name)


def generate(exam_type: str, db: Session, seed: int | None = None) -> dict:
    """Generate one cloze exam for the given exam type."""
    pool = get_pool(db)
    return _eg.generate_cloze_test(
        exam_type,
        pool=pool,
        seed=seed,
        require_real_sentence=True,
    )

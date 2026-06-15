"""Seed / import service for the vocabulary catalog.

Responsible for loading curated word data from JSON or CSV into the
``catalog_words`` table. Designed so the same code path handles the 20-word
MVP seed today and a full 10,000-word file later — just point it at a bigger
file (see ``scripts/import_vocabulary.py``).

Imports are idempotent: a word that already exists (matched by ``word``) is
skipped, so re-running is safe.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.catalog import CatalogWord

# Seed files shipped with the app. We prefer the full generated dataset
# (10,000 words) when it exists, and fall back to the small 20-word sample.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FULL_SEED_FILE = DATA_DIR / "vocabulary_full.json"
SAMPLE_SEED_FILE = DATA_DIR / "vocabulary_seed.json"


def default_seed_file() -> Path:
    """Return the best available seed file (full dataset if present)."""
    return FULL_SEED_FILE if FULL_SEED_FILE.exists() else SAMPLE_SEED_FILE


# Backwards-compatible alias.
DEFAULT_SEED_FILE = default_seed_file()

# Columns that may hold a list in CSV (pipe- or comma-separated).
_LIST_FIELDS = {"exam_category"}


def _normalize_record(raw: dict) -> dict:
    """Coerce a raw dict (from JSON or CSV) into CatalogWord kwargs."""
    record = {
        "word": (raw.get("word") or "").strip(),
        "turkish_translation": (raw.get("turkish_translation") or "").strip(),
        "pronunciation": (raw.get("pronunciation") or None),
        "audio_url": (raw.get("audio_url") or None),
        "image_url": (raw.get("image_url") or None),
        "example_sentence": (raw.get("example_sentence") or None),
        "example_sentence_tr": (raw.get("example_sentence_tr") or None),
        "level": (raw.get("level") or "intermediate").strip(),
        "word_type": (raw.get("word_type") or None),
    }

    # exam_category may arrive as a list (JSON) or a delimited string (CSV).
    exam = raw.get("exam_category")
    if isinstance(exam, str):
        parts = [p.strip() for p in exam.replace("|", ",").split(",")]
        exam = [p for p in parts if p]
    record["exam_category"] = exam or []
    return record


def load_records_from_json(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [_normalize_record(item) for item in data]


def load_records_from_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [_normalize_record(row) for row in reader]


def load_records(path: str | Path) -> list[dict]:
    """Load records from a .json or .csv file based on its extension."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return load_records_from_csv(path)
    return load_records_from_json(path)


def import_records(db: Session, records: list[dict]) -> dict:
    """Insert records, skipping words that already exist. Returns counts."""
    existing = {w for (w,) in db.query(CatalogWord.word).all()}
    added = 0
    skipped = 0

    for record in records:
        word = record.get("word")
        if not word or word in existing:
            skipped += 1
            continue
        db.add(CatalogWord(**record))
        existing.add(word)
        added += 1

    if added:
        db.commit()
    return {"added": added, "skipped": skipped, "total": len(records)}


def import_file(db: Session, path: str | Path) -> dict:
    """Convenience: load a JSON/CSV file and import it."""
    return import_records(db, load_records(path))


def seed_if_empty(db: Session, path: str | Path | None = None) -> dict:
    """Seed the catalog from the default file only if it's currently empty.

    Called on app startup. If words already exist (e.g. a full dataset was
    imported), this does nothing. When no path is given, the best available
    seed file is used (full 10k dataset if present, else the 20-word sample).
    """
    if path is None:
        path = default_seed_file()
    if db.query(CatalogWord.id).first() is not None:
        return {"added": 0, "skipped": 0, "total": 0, "note": "already seeded"}
    if not Path(path).exists():
        return {"added": 0, "skipped": 0, "total": 0, "note": "seed file missing"}
    return import_file(db, path)

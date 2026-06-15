#!/usr/bin/env python3
"""Seed the standard learning paths and link catalog words to them.

Creates the six standard paths (IELTS, TOEFL, YDS / YÖKDİL, Business English,
Academic English, Daily English) and assigns existing catalog words to them
using their level/category metadata (see
``learning_path_service.assign_paths_for_word``).

Idempotent: running it multiple times never creates duplicate paths or links.
It does NOT touch the 10,000-word catalog or any user data.

Usage (from the ``senseword/`` directory):

    python scripts/seed_learning_paths.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure ``import app`` works when run from senseword/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services import catalog_service, learning_path_service  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        catalog_total = catalog_service.count_words(db)
        if catalog_total == 0:
            print(
                "No catalog words found. Seed/import the vocabulary catalog first "
                "(e.g. start the app once, or run scripts/import_vocabulary.py)."
            )
            return

        # force=True so the full assignment pass always runs (still idempotent).
        result = learning_path_service.seed_learning_paths(db, force=True)

        # Per-path word counts for a clear summary.
        counts = learning_path_service.word_counts_for_paths(db)
        paths = learning_path_service.list_active_paths(db)

        print("Learning paths seeded.")
        print(f"  catalog words available : {catalog_total}")
        print(f"  paths created (new)     : {result['paths_created']}")
        print(f"  word-path links created : {result['links_created']}")
        print(f"  total standard paths    : {result['paths_total']}")
        print("  per-path word counts:")
        for p in paths:
            print(f"    - {p.name} [{p.slug}]: {counts.get(p.id, 0)} words")
    finally:
        db.close()


if __name__ == "__main__":
    main()

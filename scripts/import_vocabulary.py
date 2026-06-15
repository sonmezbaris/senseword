#!/usr/bin/env python3
"""Import a vocabulary dataset (JSON or CSV) into the catalog.

Usage (from the ``senseword/`` directory):

    python scripts/import_vocabulary.py path/to/vocabulary.json
    python scripts/import_vocabulary.py path/to/vocabulary.csv

The file must contain one word per row/object with the same fields as the seed
JSON (see ``app/data/vocabulary_seed.json``). Words that already exist in the
database are skipped, so you can safely re-run this to add more data.

Example for a full 10,000-word dataset later:

    python scripts/import_vocabulary.py data/vocabulary_10000.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure ``import app`` works when the script is run from senseword/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services import catalog_service, seed_service  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import vocabulary into SenseWord catalog")
    parser.add_argument("file", help="Path to a .json or .csv vocabulary file")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    init_db()
    db = SessionLocal()
    try:
        result = seed_service.import_file(db, path)
        total = catalog_service.count_words(db)
        print(
            f"Import complete: added={result['added']} "
            f"skipped={result['skipped']} "
            f"catalog_total={total}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

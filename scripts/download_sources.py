#!/usr/bin/env python3
"""Download the free, open data sources used to build the vocabulary dataset.

Run once (from the ``senseword/`` directory):

    python scripts/download_sources.py

Files are saved into ``data/`` (git-ignored). After this, run
``scripts/generate_dataset.py`` to build ``app/data/vocabulary_full.json``.

Sources (all free / open):
  * google-10000-english (frequency words) — MIT-style list
  * FreeDict eng-tur (translations) — GPL/CC
  * ipa-dict en_US (IPA) — MIT
  * OPUS Tatoeba en-tr (example sentences) — CC-BY 2.0
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UA = {"User-Agent": "Mozilla/5.0 (SenseWord dataset builder)"}

PLAIN_FILES = {
    "freq_words.txt": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt",
    "eng-tur.tei": "https://raw.githubusercontent.com/freedict/fd-dictionaries/master/eng-tur/eng-tur.tei",
    "ipa_en_US.txt": "https://raw.githubusercontent.com/open-dict-data/ipa-dict/master/data/en_US.txt",
}

TATOEBA_ZIP = "https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/moses/en-tr.txt.zip"


def _download(url: str, dest: Path) -> None:
    print(f"  downloading {dest.name} ...")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for name, url in PLAIN_FILES.items():
        _download(url, DATA_DIR / name)

    print("  downloading + extracting Tatoeba en-tr sentence pairs ...")
    req = urllib.request.Request(TATOEBA_ZIP, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in zf.namelist():
            if member.endswith((".en", ".tr")):
                zf.extract(member, DATA_DIR)

    print(f"Done. Sources are in {DATA_DIR}")


if __name__ == "__main__":
    main()

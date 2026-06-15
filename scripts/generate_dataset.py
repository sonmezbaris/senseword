#!/usr/bin/env python3
"""Generate a 10,000-word English→Turkish vocabulary dataset.

This builds ``app/data/vocabulary_full.json`` (the dataset the study screen
uses) by combining several free, open data sources that are downloaded into
``data/`` by ``scripts/download_sources.py``:

  * google-10000-english .... frequency-ranked English words (importance order)
  * FreeDict eng-tur ......... real Turkish translations
  * ipa-dict en_US ........... IPA pronunciation text
  * OPUS Tatoeba en-tr ....... real, paired example sentences (EN + TR)

For every word we also attach:
  * image_url  -> a keyword image service (works for any word, no files needed)
  * audio_url  -> left empty on purpose: the app speaks the word AND the example
                  sentence with the browser's text-to-speech, so every one of
                  the 10,000 words has working pronunciation audio without
                  shipping 10,000 audio files. (Swap in a real TTS URL later.)

Run (from the ``senseword/`` directory):

    python scripts/download_sources.py     # one-time: fetch source files
    python scripts/generate_dataset.py      # build the 10k JSON

The result is idempotent and safe to re-run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_FILE = ROOT / "app" / "data" / "vocabulary_full.json"

TARGET_COUNT = 30_000

# Image service: keyword-based real photos, no API key required. The study UI
# hides the image gracefully if a particular request fails.
IMAGE_URL_TEMPLATE = "https://loremflickr.com/400/320/{word}"

# Turkish POS abbreviations sometimes embedded in FreeDict translations.
_POS_MARKERS = {
    "f.": "verb",      # fiil
    "i.": "noun",      # isim
    "s.": "adjective", # sıfat
    "z.": "adverb",    # zarf
}


# ---------------------------------------------------------------------------
# Source loaders
# ---------------------------------------------------------------------------
def load_frequency_words() -> list[str]:
    """Frequency-ordered English words (most common first)."""
    path = DATA_DIR / "freq_words.txt"
    words = []
    for line in path.read_text(encoding="utf-8").split():
        w = line.strip().lower()
        if w.isalpha() and len(w) > 1:
            words.append(w)
    # De-duplicate while preserving order.
    seen = set()
    ordered = []
    for w in words:
        if w not in seen:
            seen.add(w)
            ordered.append(w)
    return ordered


def load_translations() -> dict[str, str]:
    """Parse FreeDict TEI: English headword -> first Turkish translation."""
    path = DATA_DIR / "eng-tur.tei"
    text = path.read_text(encoding="utf-8")
    translations: dict[str, str] = {}

    # Each <entry> has one <orth> (headword) and one or more <quote> (Turkish).
    for entry in re.findall(r"<entry>.*?</entry>", text, re.S):
        orth_m = re.search(r"<orth>(.*?)</orth>", entry, re.S)
        quote_m = re.search(r"<quote>(.*?)</quote>", entry, re.S)
        if not orth_m or not quote_m:
            continue
        word = orth_m.group(1).strip().lower()
        tr = _clean_translation(quote_m.group(1))
        if word and tr and word not in translations:
            translations[word] = tr
    return translations


def _clean_translation(raw: str) -> str:
    """Tidy a Turkish translation string for display."""
    tr = re.sub(r"\s+", " ", raw).strip()
    # Drop leading parenthetical domain tags like "(müz.)" for a cleaner label.
    tr = re.sub(r"^\([^)]*\)\s*", "", tr)
    # Strip trailing punctuation artifacts (e.g. "write." -> "write").
    tr = tr.rstrip(" .;:,")
    # Keep it short and readable.
    if len(tr) > 60:
        tr = tr[:57].rstrip() + "..."
    return tr


def detect_word_type(translation_raw: str) -> str | None:
    for marker, pos in _POS_MARKERS.items():
        if marker in translation_raw:
            return pos
    return None


def load_ipa() -> dict[str, str]:
    """word -> IPA string (first variant)."""
    path = DATA_DIR / "ipa_en_US.txt"
    ipa: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        word, prons = line.split("\t", 1)
        word = word.strip().lower()
        first = prons.split(",")[0].strip()
        if word and first:
            ipa[word] = first
    return ipa


def build_sentence_index(target_words: set[str]) -> dict[str, tuple[str, str]]:
    """word -> (english_sentence, turkish_sentence) using paired Tatoeba data.

    For each target word we keep the *shortest* clean sentence that contains
    it as a whole word — shorter sentences are easier for learners.
    """
    en_path = DATA_DIR / "Tatoeba.en-tr.en"
    tr_path = DATA_DIR / "Tatoeba.en-tr.tr"

    best: dict[str, tuple[int, str, str]] = {}  # word -> (len, en, tr)
    token_re = re.compile(r"[a-zA-Z]+")

    def scan(min_len: int, max_len: int, strict: bool, remaining: set[str]) -> None:
        with open(en_path, encoding="utf-8") as fen, open(tr_path, encoding="utf-8") as ftr:
            for en_line, tr_line in zip(fen, ftr):
                en = en_line.strip()
                tr = tr_line.strip()
                length = len(en)
                if not (min_len <= length <= max_len):
                    continue
                if strict and (not en[:1].isupper() or en[-1] not in ".!?"):
                    continue
                if not en or not tr:
                    continue
                tokens = {t.lower() for t in token_re.findall(en)}
                relevant = tokens & remaining
                for w in relevant:
                    prev = best.get(w)
                    if prev is None or length < prev[0]:
                        best[w] = (length, en, tr)

    # Pass 1: short, well-formed sentences (best quality).
    scan(15, 80, strict=True, remaining=target_words)
    # Pass 2: relaxed constraints for words still without a sentence.
    remaining = target_words - set(best.keys())
    if remaining:
        scan(10, 110, strict=False, remaining=remaining)

    return {w: (v[1], v[2]) for w, v in best.items()}


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------
def level_for_rank(rank: int) -> str:
    # Keep the level split proportional to the dataset size (~20% / 30% / 50%),
    # so the study level tabs stay balanced regardless of TARGET_COUNT.
    if rank < TARGET_COUNT * 0.2:
        return "beginner"
    if rank < TARGET_COUNT * 0.5:
        return "intermediate"
    return "advanced"


def exam_categories_for(level: str) -> list[str]:
    return {
        "beginner": ["general"],
        "intermediate": ["TOEFL", "IELTS", "general"],
        "advanced": ["GRE", "SAT", "academic"],
    }[level]


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def build_entry(word: str, rank: int, translation: str, ipa: str | None,
                sentence: tuple[str, str] | None, word_type: str | None) -> dict:
    level = level_for_rank(rank)
    example_en, example_tr = sentence if sentence else (None, None)
    if not example_en:
        # Simple, grammatical fallback that still uses the word in context.
        example_en = f"This is an example with the word \"{word}\"."
        example_tr = f"Bu, \"{translation}\" kelimesini içeren bir örnektir."

    return {
        "word": word,
        "turkish_translation": translation,
        "pronunciation": ipa or "",
        # Empty audio_url -> the app uses browser text-to-speech for word + sentence.
        "audio_url": "",
        "image_url": IMAGE_URL_TEMPLATE.format(word=word),
        "example_sentence": example_en,
        "example_sentence_tr": example_tr,
        "level": level,
        "exam_category": exam_categories_for(level),
        "word_type": word_type,
    }


def main() -> None:
    print("Loading sources...")
    freq = load_frequency_words()
    translations = load_translations()
    ipa = load_ipa()
    print(f"  frequency words: {len(freq)}")
    print(f"  translations:    {len(translations)}")
    print(f"  ipa entries:     {len(ipa)}")

    # 1) Prioritize frequency-ranked words that have a translation.
    chosen: list[str] = []
    chosen_set: set[str] = set()
    for w in freq:
        if w in translations and w not in chosen_set:
            chosen.append(w)
            chosen_set.add(w)
        if len(chosen) >= TARGET_COUNT:
            break

    # 2) Top up from the rest of the dictionary if we still need more.
    if len(chosen) < TARGET_COUNT:
        for w in sorted(translations.keys()):
            if w not in chosen_set and w.isalpha():
                chosen.append(w)
                chosen_set.add(w)
            if len(chosen) >= TARGET_COUNT:
                break

    chosen = chosen[:TARGET_COUNT]
    print(f"Selected {len(chosen)} words.")

    print("Indexing example sentences (this scans ~677k pairs)...")
    sentence_index = build_sentence_index(set(chosen))
    print(f"  matched sentences for {len(sentence_index)} words.")

    print("Assembling entries...")
    entries = []
    for rank, word in enumerate(chosen):
        # Re-read the raw translation to detect POS markers before cleaning.
        translation = translations[word]
        entries.append(
            build_entry(
                word=word,
                rank=rank,
                translation=translation,
                ipa=ipa.get(word),
                sentence=sentence_index.get(word),
                word_type=detect_word_type(translation),
            )
        )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with_sentence = sum(1 for e in entries if "example with the word" not in (e["example_sentence"] or ""))
    with_ipa = sum(1 for e in entries if e["pronunciation"])
    print(
        f"Wrote {len(entries)} entries to {OUT_FILE}\n"
        f"  with real example sentence: {with_sentence}\n"
        f"  with IPA pronunciation:     {with_ipa}"
    )


if __name__ == "__main__":
    main()

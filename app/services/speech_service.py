"""Speech service abstraction.

For the MVP, text-to-speech and speech recognition happen entirely in the
browser (Web Speech API), so this service mostly provides metadata and a
clean seam for adding a real backend TTS/STT provider later (e.g. Google
Cloud, Azure, or an AI model). Keeping it here means routers/templates don't
need to change when we switch implementations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PronunciationGuide:
    """Everything the frontend needs to pronounce a word."""

    text: str
    lang: str = "en-US"
    # When a backend TTS provider is added this can hold an audio URL.
    audio_url: str | None = None


def get_pronunciation_guide(word: str, pronunciation: str | None = None) -> PronunciationGuide:
    """Return pronunciation info for a word.

    MVP: we just hand the text back to the browser's speechSynthesis. The
    optional ``pronunciation`` field (e.g. an IPA or phonetic hint) is passed
    through for display purposes.
    """
    return PronunciationGuide(text=word)


def evaluate_pronunciation(target: str, spoken: str) -> dict:
    """Naive comparison of recognized speech against the target word/sentence.

    MVP heuristic: case-insensitive token overlap -> a 0..1 score. This is a
    placeholder for a future AI-based pronunciation scorer.
    """
    target_tokens = set(target.lower().split())
    spoken_tokens = set(spoken.lower().split())
    if not target_tokens:
        return {"score": 0.0, "matched": [], "missed": []}

    matched = target_tokens & spoken_tokens
    missed = target_tokens - spoken_tokens
    score = round(len(matched) / len(target_tokens), 2)
    return {
        "score": score,
        "matched": sorted(matched),
        "missed": sorted(missed),
    }

"""Pronunciation service.

Generates IPA-style pronunciation text for an English word.

MVP implementation: a small built-in dictionary of common words. Unknown
words fall back to returning the word itself. The single ``get_pronunciation``
entry point is intentionally the only public API so that, later, the body can
be swapped for an external dictionary API (e.g. Free Dictionary API) or an AI
service without touching routers, templates, or JavaScript.
"""

from __future__ import annotations

# Minimal seed dictionary for the MVP. Extend freely or replace with a real
# data source later. Keys are stored lowercase for case-insensitive lookup.
_PRONUNCIATION_DICT: dict[str, str] = {
    "apple": "/ˈæp.əl/",
    "run": "/rʌn/",
    "happy": "/ˈhæp.i/",
    "window": "/ˈwɪn.doʊ/",
    "mountain": "/ˈmaʊn.tən/",
    "book": "/bʊk/",
    "water": "/ˈwɔː.tər/",
    "remember": "/rɪˈmem.bər/",
    "quickly": "/ˈkwɪk.li/",
    "beautiful": "/ˈbjuː.t̬ə.fəl/",
}


def get_pronunciation(word: str) -> str:
    """Return the pronunciation text for ``word``.

    Looks the word up (case-insensitively) in the built-in dictionary. If it
    is not found, the word itself is returned as a safe fallback.

    Args:
        word: The English word to look up.

    Returns:
        An IPA-style pronunciation string, or the original word if unknown.
    """
    normalized = word.strip().lower()
    if not normalized:
        return ""
    return _PRONUNCIATION_DICT.get(normalized, word.strip())

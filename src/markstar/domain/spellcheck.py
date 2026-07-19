"""Spellcheck: a pure misspelling finder + a pyspellchecker-backed speller.

``find_misspellings`` is pure and testable (it takes a ``known(word)`` callable,
no dictionary import). ``Speller`` wraps pyspellchecker — pure Python, bundled
English dictionary, no system dependency — and layers a personal dictionary
(added words) and a session ignore-set on top.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

from markstar.domain.search import Match

_WORD = re.compile(r"[A-Za-z][A-Za-z']*")
_URL = re.compile(r"https?://\S+|www\.\S+")
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_FENCE = re.compile(r"^\s*(?:```|~~~)")


def _mask(line: str) -> str:
    """Blank out URLs and inline code (same length) so their words are skipped
    while column offsets stay aligned to the original line."""
    chars = list(line)
    for pattern in (_URL, _INLINE_CODE):
        for m in pattern.finditer(line):
            for i in range(m.start(), m.end()):
                chars[i] = " "
    return "".join(chars)


def find_misspellings(text: str, known: Callable[[str], bool]) -> list[Match]:
    """Return document spans of words ``known`` reports as misspelled.

    Skips fenced code blocks, inline code, URLs, words shorter than 2 chars,
    and words containing digits.
    """
    matches: list[Match] = []
    in_fence = False
    offset = 0
    for line in text.split("\n"):
        line_len = len(line)
        if _FENCE.match(line):
            in_fence = not in_fence
            offset += line_len + 1
            continue
        if in_fence:
            offset += line_len + 1
            continue
        for m in _WORD.finditer(_mask(line)):
            word = m.group(0)
            if len(word.strip("'")) < 2 or any(c.isdigit() for c in word):
                continue
            if known(word):
                continue
            matches.append(Match(offset + m.start(), offset + m.end()))
        offset += line_len + 1
    return matches


class Speller:
    """English speller with a personal dictionary and session ignore-set.

    The underlying pyspellchecker dictionary loads lazily on first use (it is a
    few MB); callers that care about latency should prime it off the UI thread.
    """

    def __init__(self, added: Iterable[str] = ()) -> None:
        self._sp = None
        self._added: set[str] = {w.lower() for w in added}
        self._ignored: set[str] = set()

    def _ensure(self) -> None:
        if self._sp is None:
            from spellchecker import SpellChecker

            self._sp = SpellChecker()

    def prime(self) -> None:
        """Load the dictionary now (safe to call from a worker thread)."""
        self._ensure()

    def known(self, word: str) -> bool:
        w = word.lower()
        if w in self._added or w in self._ignored:
            return True
        self._ensure()
        return len(self._sp.known([w])) > 0

    def suggestions(self, word: str, limit: int = 8) -> list[str]:
        self._ensure()
        cands = self._sp.candidates(word.lower()) or set()
        cands.discard(word.lower())
        ranked = sorted(cands, key=lambda c: self._sp.word_frequency[c], reverse=True)
        return ranked[:limit]

    def add(self, word: str) -> None:
        """Add to the personal dictionary (persisted by the caller)."""
        self._added.add(word.lower())

    def ignore(self, word: str) -> None:
        """Ignore for this session only."""
        self._ignored.add(word.lower())

    @property
    def added_words(self) -> list[str]:
        return sorted(self._added)

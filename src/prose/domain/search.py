"""Find / replace helpers (pure functions over text + Document)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from prose.domain.document import Document


@dataclass(frozen=True)
class Match:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def find_next(
    text: str,
    query: str,
    *,
    start: int = 0,
    case_sensitive: bool = False,
) -> Optional[Match]:
    """First match at or after ``start``. Wraps from beginning if none found after start."""
    if not query:
        return None
    hay, needle = _normalize(text, query, case_sensitive)
    idx = hay.find(needle, start)
    if idx == -1 and start > 0:
        idx = hay.find(needle, 0)
    if idx == -1:
        return None
    return Match(idx, idx + len(query))


def find_prev(
    text: str,
    query: str,
    *,
    start: int = 0,
    case_sensitive: bool = False,
) -> Optional[Match]:
    """Nearest match that *starts* before ``start``. Wraps to the last match."""
    if not query:
        return None
    matches = find_all(text, query, case_sensitive=case_sensitive)
    if not matches:
        return None
    earlier = [m for m in matches if m.start < start]
    if earlier:
        return earlier[-1]
    return matches[-1]


def step_find(
    text: str,
    query: str,
    *,
    direction: str,
    cursor: int = 0,
    current_start: int | None = None,
    case_sensitive: bool = False,
) -> Optional[Match]:
    """Step to the next/previous match in document order, wrapping at ends.

    If ``current_start`` is the start index of the focused match, step from
    that hit. Otherwise land on the first match at/after ``cursor`` (next)
    or the last match before ``cursor`` (prev).
    """
    if direction not in ("next", "prev"):
        raise ValueError(f"direction must be 'next' or 'prev', got {direction!r}")
    matches = find_all(text, query, case_sensitive=case_sensitive)
    if not matches:
        return None

    current_idx: int | None = None
    if current_start is not None:
        for i, m in enumerate(matches):
            if m.start == current_start:
                current_idx = i
                break

    n = len(matches)
    if current_idx is not None:
        if direction == "next":
            return matches[(current_idx + 1) % n]
        return matches[(current_idx - 1) % n]

    if direction == "next":
        for m in matches:
            if m.start >= cursor:
                return m
        return matches[0]

    for m in reversed(matches):
        if m.start < cursor:
            return m
    return matches[-1]


def find_all(
    text: str,
    query: str,
    *,
    case_sensitive: bool = False,
) -> list[Match]:
    if not query:
        return []
    hay, needle = _normalize(text, query, case_sensitive)
    matches: list[Match] = []
    pos = 0
    while True:
        idx = hay.find(needle, pos)
        if idx == -1:
            break
        matches.append(Match(idx, idx + len(query)))
        pos = idx + max(len(needle), 1)
    return matches


def replace_all(
    document: Document,
    query: str,
    replacement: str,
    *,
    case_sensitive: bool = False,
) -> int:
    """Replace every non-overlapping match. Returns number of replacements.

    One undo step for the whole buffer change.
    """
    if not query:
        return 0
    matches = find_all(document.text, query, case_sensitive=case_sensitive)
    if not matches:
        return 0
    text = document.text
    # Build new text from the end so offsets stay valid
    pieces: list[str] = []
    last = len(text)
    for match in reversed(matches):
        pieces.append(text[match.end : last])
        pieces.append(replacement)
        last = match.start
    pieces.append(text[:last])
    new_text = "".join(reversed(pieces))
    document.set_text(new_text)
    return len(matches)


def replace_match(
    document: Document,
    match: Match,
    replacement: str,
) -> Match:
    """Replace one match; returns the span of the inserted replacement."""
    document.replace(match.start, match.end, replacement)
    return Match(match.start, match.start + len(replacement))


def _normalize(text: str, query: str, case_sensitive: bool) -> tuple[str, str]:
    if case_sensitive:
        return text, query
    return text.lower(), query.lower()

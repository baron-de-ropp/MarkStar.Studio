"""Subsequence fuzzy matching for quick-open.

Type "ch3" and reach "books/deathbringer/chapter-3.md". A candidate matches when
the query appears in it as a subsequence (same order, gaps allowed); the score
then rewards the matches a human would call obvious — unbroken runs, word
starts, and hits in the filename rather than the folders above it.

Pure: no filesystem, no Textual. See domain/filewalk for candidate gathering.
"""

from __future__ import annotations

# Scoring weights. Relative size is what matters: a filename hit should beat a
# folder hit outright, and an unbroken run should beat scattered letters.
_BASENAME = 40      # the whole query fits inside the filename
_HEAD = 10          # matched the first character of the region
_WORD_START = 6     # matched just after a separator
_CONSECUTIVE = 8    # matched immediately after the previous match
_RECENT = 25        # boost applied to entries the writer opened lately
_MAX_LEN_PENALTY = 20  # long paths lose a little, but never rank below noise

_SEPARATORS = " -_./\\"


def _subsequence_score(query: str, text: str, start: int) -> int | None:
    """Greedy left-to-right subsequence match of ``query`` in ``text[start:]``.

    Returns the bonus total, or None when ``text`` doesn't contain the query.
    Greedy (first match wins) rather than optimal: it is linear, and for path
    fragments the first match is nearly always the one the writer meant.
    """
    score = 0
    pos = start
    prev_end = -1
    for ch in query:
        found = text.find(ch, pos)
        if found < 0:
            return None
        if found == prev_end:
            score += _CONSECUTIVE
        if found == start:
            score += _HEAD
        elif found > 0 and text[found - 1] in _SEPARATORS:
            score += _WORD_START
        prev_end = found + 1
        pos = found + 1
    return score


def fuzzy_score(query: str, candidate: str) -> int | None:
    """Score ``candidate`` against ``query`` (higher is better), None if no match.

    An empty query matches everything at 0, so the caller's incoming order (the
    recents list) survives untouched.
    """
    if not query:
        return 0
    q = query.lower()
    cand = candidate.lower()
    penalty = min(len(candidate), _MAX_LEN_PENALTY)

    # Try the filename alone first: "chap" should find chapter.md before it
    # finds notes/chapel-research/unrelated.md.
    base_start = max(cand.rfind("/"), cand.rfind("\\")) + 1
    base = _subsequence_score(q, cand, base_start)
    if base is not None:
        return base + _BASENAME - penalty

    whole = _subsequence_score(q, cand, 0)
    if whole is None:
        return None
    return whole - penalty


def rank(
    query: str,
    candidates: list[str],
    *,
    limit: int = 50,
    boost: frozenset[str] | set[str] = frozenset(),
) -> list[str]:
    """Best matches first. ``boost`` entries (recents) float above equal scores.

    Ties break on the incoming index, so equal-scoring candidates keep the order
    they arrived in — recents stay in recency order, project files stay sorted.
    """
    scored: list[tuple[int, int, str]] = []
    for i, cand in enumerate(candidates):
        score = fuzzy_score(query, cand)
        if score is None:
            continue
        if cand in boost:
            score += _RECENT
        scored.append((-score, i, cand))
    scored.sort()
    return [cand for _, _, cand in scored[:limit]]

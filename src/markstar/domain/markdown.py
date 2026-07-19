"""Pure Markdown logic — inline styling spans and marker-toggle editing.

No Textual / UI imports: everything here is a pure function over plain strings,
so it is unit-testable in isolation. The app layer adapts these to the editor
widget (reading the caret/selection, applying the returned text).

Design (approach #1): style spans never *hide* characters, so document columns
map 1:1 to screen columns — there is no source↔screen offset to track.
"""

from __future__ import annotations

import re

# Inline Markdown patterns.
RE_HEADING = re.compile(r"^(#{1,6}\s+)(.*)$")
RE_QUOTE = re.compile(r"^(\s*>\s?)(.*)$")
# List marker at line start: -, +, * (bullet) or "1." (ordered), then a space.
# The trailing space distinguishes "* item" (bullet) from "*italic*".
RE_LIST = re.compile(r"^(\s*(?:[-+*]|\d+\.)\s+)")
# [text](url) — dim the brackets/url, color the link text.
RE_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")
# ![[name]] — a MarkStar include token (expanded only on compile).
RE_INCLUDE = re.compile(r"!\[\[[^\]\n]+\]\]")
RE_CODE = re.compile(r"`([^`\n]+)`")
RE_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)")
RE_STRIKE = re.compile(r"~~([^~\n]+)~~")
# A fenced-code delimiter line: ``` or ~~~ (3+), optionally indented, with an
# optional info string (language) after it. Fences span multiple lines, so they
# are tracked separately by the editor (not here).
RE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def word_bounds(line: str, col: int) -> tuple[int, int]:
    """Expand ``col`` to the word (letters/digits/apostrophes) around it."""
    n = len(line)
    col = max(0, min(col, n))

    def is_word(ch: str) -> bool:
        return ch.isalnum() or ch == "'"

    start = col
    while start > 0 and is_word(line[start - 1]):
        start -= 1
    end = col
    while end < n and is_word(line[end]):
        end += 1
    return start, end


def markdown_spans(line: str) -> list[tuple[int, int, str]]:
    """Return (start, end, style-key) spans for inline Markdown on one line.

    Markers (``**``, ``*``, `` ` ``, ``~~``, ``#``, ``>``) get the ``marker``
    key so they render dimmed; the wrapped content gets its semantic key.
    Characters are never removed, so columns map 1:1 to the document.
    (Fenced code blocks are handled per-line by the editor, not here.)
    """
    spans: list[tuple[int, int, str]] = []
    heading = RE_HEADING.match(line)
    if heading:
        marker_end = len(heading.group(1))
        spans.append((0, marker_end, "marker"))
        spans.append((marker_end, len(line), "heading"))
        return spans
    quote = RE_QUOTE.match(line)
    if quote:
        marker_end = len(quote.group(1))
        spans.append((0, marker_end, "marker"))
        spans.append((marker_end, len(line), "quote"))
        return spans
    # List marker (bullet/ordered): dim just the marker, then keep going so
    # inline formatting inside the item still renders.
    lst = RE_LIST.match(line)
    if lst:
        spans.append((0, len(lst.group(1)), "marker"))
    # Includes: ![[name]] — a whole-token highlight (expanded only on compile).
    for m in RE_INCLUDE.finditer(line):
        spans.append((m.start(), m.end(), "include"))
    # Links: [text](url) — color the text, dim the [] () and the url.
    for m in RE_LINK.finditer(line):
        text_start = m.start() + 1
        text_end = text_start + len(m.group(1))
        spans.append((m.start(), text_start, "marker"))  # [
        spans.append((text_start, text_end, "link"))     # text
        spans.append((text_end, m.end(), "marker"))      # ](url)
    for rx, mlen, kind in (
        (RE_CODE, 1, "code"),
        (RE_BOLD, 2, "strong"),
        (RE_ITALIC, 1, "emphasis"),
        (RE_STRIKE, 2, "strike"),
    ):
        for m in rx.finditer(line):
            spans.append((m.start(), m.start() + mlen, "marker"))
            spans.append((m.start() + mlen, m.end() - mlen, kind))
            spans.append((m.end() - mlen, m.end(), "marker"))
    return spans


def toggle_emphasis(
    line: str, marker: str, regex: "re.Pattern[str]", a: int, b: int, caret: int
) -> tuple[str, int]:
    """Toggle ``marker`` (``**``, ``*``, ``~~``, `` ` ``) over ``line[a:b]``.

    If ``line[a:b]`` already sits inside a match of ``regex`` (i.e. it's already
    emphasized) the markers are stripped; otherwise the range is wrapped. Returns
    the rewritten line and the new caret column, both adjusted for the change.
    Pure: the caller supplies the range and caret and applies the result.
    """
    mlen = len(marker)
    enclosing = None
    for m in regex.finditer(line):
        if m.start() <= a and b <= m.end():
            enclosing = m
            break

    if enclosing is not None:  # already emphasized → strip markers
        s, e = enclosing.start(), enclosing.end()
        new_line = line[:s] + line[s + mlen : e - mlen] + line[e:]
        if caret <= s:
            nc = caret
        elif caret <= s + mlen:
            nc = s
        elif caret <= e - mlen:
            nc = caret - mlen
        else:
            nc = caret - 2 * mlen
    else:  # wrap the range (or insert empty markers at a bare caret)
        new_line = line[:a] + marker + line[a:b] + marker + line[b:]
        if caret <= a:
            nc = caret
        elif caret <= b:
            nc = caret + mlen
        else:
            nc = caret + 2 * mlen
    return new_line, max(0, min(nc, len(new_line)))

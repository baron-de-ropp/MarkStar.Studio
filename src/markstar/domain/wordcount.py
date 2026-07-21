"""Word counts a novelist would recognise.

``len(text.split())`` counts ``**bold**`` as one word made of ten characters,
four of which are asterisks, and counts a fenced code block, a link's URL, and
an ``![[include]]`` token as prose. A manuscript count has to mean "words a
reader will read", so the markup is stripped before anything is counted.

Pure: strings in, numbers out. Reuses the patterns in domain/markdown so there
is exactly one Markdown dialect in this codebase.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from markstar.domain.markdown import (
    RE_FENCE,
    RE_HEADING,
    RE_INCLUDE,
    RE_LIST,
    RE_QUOTE,
)

# Inline markers to unwrap, in the order they must be applied: bold before
# italic (``**x**`` would otherwise be read as an italic ``*`` pair), and code
# spans before either, since their contents are not prose at all.
_RE_CODE_SPAN = re.compile(r"`[^`\n]*`")
_RE_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")          # keep the text
_RE_IMAGE = re.compile(r"!\[([^\]\n]*)\]\([^)\n]*\)")        # keep the alt text
_RE_AUTOLINK = re.compile(r"<https?://[^>\n]+>")
_RE_BOLD = re.compile(r"\*\*([^*\n]+)\*\*|__([^_\n]+)__")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)|(?<!_)_(?!_)([^_\n]+?)_(?!_)")
_RE_STRIKE = re.compile(r"~~([^~\n]+)~~")
_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_HTML_TAG = re.compile(r"</?[A-Za-z][^>\n]*>")
_RE_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_RE_TABLE_RULE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


class Counts(NamedTuple):
    words: int
    characters: int


def _strip_inline(line: str) -> str:
    """Remove inline markup from one line, keeping the words a reader sees."""
    line = _RE_IMAGE.sub(r"\1", line)      # before links: images are ![...](...)
    line = _RE_LINK.sub(r"\1", line)
    line = _RE_AUTOLINK.sub(" ", line)
    line = _RE_CODE_SPAN.sub(" ", line)    # code is not prose
    line = _RE_BOLD.sub(lambda m: m.group(1) or m.group(2) or "", line)
    line = _RE_ITALIC.sub(lambda m: m.group(1) or m.group(2) or "", line)
    line = _RE_STRIKE.sub(r"\1", line)
    line = _RE_HTML_TAG.sub(" ", line)
    return line


def prose_text(markdown: str) -> str:
    """The readable prose of a Markdown document, with markup removed.

    Fenced code blocks are dropped whole. Headings, blockquotes and list
    markers lose their markers but keep their words — a chapter title is text
    the reader reads. Include tokens, HTML comments (author notes) and link
    URLs are dropped entirely.
    """
    if not markdown:
        return ""
    text = _RE_HTML_COMMENT.sub(" ", markdown)

    out: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.split("\n"):
        fence = RE_FENCE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, ""
            continue  # the delimiter line itself is never prose
        if in_fence:
            continue

        line = RE_INCLUDE.sub(" ", line)
        if _RE_RULE.match(line) or _RE_TABLE_RULE.match(line):
            continue  # horizontal rules and table separators carry no words

        heading = RE_HEADING.match(line)
        if heading:
            line = heading.group(2)
        else:
            quote = RE_QUOTE.match(line)
            if quote:
                line = quote.group(2)
            line = RE_LIST.sub("", line)

        out.append(_strip_inline(line))
    return "\n".join(out)


def count(markdown: str) -> Counts:
    """Words and characters of the prose in a Markdown document."""
    prose = prose_text(markdown)
    words = len(prose.split())
    # Characters as a reader meets them: collapse the whitespace the markup
    # stripping left behind, but keep the spaces between words.
    characters = len(re.sub(r"[ \t]+", " ", prose).strip())
    return Counts(words=words, characters=characters)

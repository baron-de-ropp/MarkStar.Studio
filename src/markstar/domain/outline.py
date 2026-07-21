"""The shape of a document, read from its Markdown headings.

A supplement's structure is already written down — every `##` is a room, an
appendix, a scene. Nothing needs marking by hand the way WordStar's numbered
place markers did; the manuscript is its own table of contents.
"""

from __future__ import annotations

from typing import NamedTuple

from markstar.domain.markdown import RE_FENCE, RE_HEADING


class Heading(NamedTuple):
    level: int   # 1-6, from the number of #
    text: str    # the heading without its markers
    line: int    # 0-based line index


def headings(markdown: str) -> list[Heading]:
    """Every heading in document order, skipping anything inside a code fence.

    A `# comment` in a shell example is not a chapter, so fenced regions are
    tracked and ignored — the same rule the editor's own highlighting uses.
    """
    out: list[Heading] = []
    in_fence = False
    fence_marker = ""
    for i, line in enumerate(markdown.split("\n")):
        fence = RE_FENCE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, ""
            continue
        if in_fence:
            continue
        match = RE_HEADING.match(line)
        if match:
            text = match.group(2).strip()
            # Trailing hashes are decoration in "## Title ##" style headings.
            text = text.rstrip("#").strip() or "(untitled)"
            out.append(Heading(len(match.group(1).strip()), text, i))
    return out

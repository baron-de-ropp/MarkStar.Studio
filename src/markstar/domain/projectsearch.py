"""Find a phrase across every document in a project.

A thirty-file supplement can't be searched by opening each chapter in turn.
Bounded on purpose: a writer's project is not a codebase, and an unbounded
grep over a home directory would be the wrong kind of thorough. When a limit
does bite, the caller is told — silent truncation reads as "nothing more to
find", which is a lie.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from markstar.domain.filewalk import list_project_files
from markstar.domain.search import find_all, replace_all
from markstar.domain.document import Document

MAX_FILE_BYTES = 2_000_000   # skip anything that isn't plausibly a manuscript
MAX_HITS = 500               # a results list nobody would scroll past
CONTEXT_CHARS = 120          # preview length per hit


class Hit(NamedTuple):
    path: Path        # absolute
    relative: str     # project-relative, for display
    line: int         # 0-based
    column: int       # 0-based, within the line
    preview: str      # the matching line, trimmed


class Results(NamedTuple):
    hits: list[Hit]
    files_searched: int
    truncated: bool   # a limit stopped the search before it finished


class ReplaceResult(NamedTuple):
    replacements: int
    files_changed: int
    files_searched: int


def search_project(
    root: Path | str,
    query: str,
    *,
    case_sensitive: bool = False,
    max_hits: int = MAX_HITS,
) -> Results:
    """Every occurrence of ``query`` under ``root``, in file then line order."""
    if not query:
        return Results([], 0, False)
    root = Path(root)
    hits: list[Hit] = []
    searched = 0
    truncated = False

    for rel in list_project_files(root):
        path = root / rel
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        searched += 1

        matches = find_all(text, query, case_sensitive=case_sensitive)
        if not matches:
            continue
        # Map character offsets onto line/column once per file rather than
        # per match — line starts are strictly increasing, so one pass does it.
        starts: list[int] = [0]
        for ch in text.split("\n")[:-1]:
            starts.append(starts[-1] + len(ch) + 1)
        lines = text.split("\n")

        line_no = 0
        for m in matches:
            while line_no + 1 < len(starts) and starts[line_no + 1] <= m.start:
                line_no += 1
            column = m.start - starts[line_no]
            preview = lines[line_no].strip()
            if len(preview) > CONTEXT_CHARS:
                preview = preview[:CONTEXT_CHARS].rstrip() + "…"
            hits.append(Hit(path, rel, line_no, column, preview))
            if len(hits) >= max_hits:
                return Results(hits, searched, True)
    return Results(hits, searched, truncated)


def replace_in_project(
    root: Path | str,
    query: str,
    replacement: str,
    *,
    case_sensitive: bool = False,
) -> ReplaceResult:
    """Replace ``query`` with ``replacement`` in every project document on disk.

    Reads and writes each openable file under ``root``. Returns how many
    substitutions ran and how many files changed. Empty query is a no-op.
    """
    if not query:
        return ReplaceResult(0, 0, 0)
    root = Path(root)
    replacements = 0
    files_changed = 0
    searched = 0
    for rel in list_project_files(root):
        path = root / rel
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        searched += 1
        doc = Document(text)
        n = replace_all(doc, query, replacement, case_sensitive=case_sensitive)
        if n == 0:
            continue
        try:
            path.write_text(doc.text, encoding="utf-8")
        except OSError:
            continue
        replacements += n
        files_changed += 1
    return ReplaceResult(replacements, files_changed, searched)

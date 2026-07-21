"""Which files MarkStar can edit, and how to enumerate a project's worth of them.

``is_openable`` is the one place that answers "is this a document?" — the tree
uses it to decide what to brighten, quick-open uses it to decide what to list.
``list_project_files`` walks a project root under hard caps so a quick-open over
someone's entire home directory can't hang the editor.
"""

from __future__ import annotations

import os
from pathlib import Path

# Files MarkStar can open/edit as documents. Everything else (images, PDFs,
# binaries, source files) still shows in the tree as a link/embed target, but is
# rendered fainter and can't be opened in an editor tab.
MARKDOWN_EXTS = frozenset(
    {".md", ".markdown", ".mdown", ".mkd", ".mdx", ".mdtext", ".txt"}
)

# Never worth walking for a writer: build output, vendored code, VCS internals.
IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".ruff_cache",
    }
)


def is_openable(path) -> bool:
    """True if ``path`` is a Markdown/plain-text document MarkStar can edit."""
    return Path(path).suffix.lower() in MARKDOWN_EXTS


def list_project_files(
    root: Path | str, *, max_files: int = 2000, max_visited: int = 20000
) -> list[str]:
    """Openable files under ``root``, as root-relative POSIX paths.

    Hidden and ignored directories are pruned before descending. Two caps bound
    the work: ``max_files`` results and ``max_visited`` filesystem entries
    examined — whichever trips first stops the walk. Truncation is silent by
    design here; the caller decides whether to say so.
    """
    root = Path(root)
    out: list[str] = []
    visited = 0
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        # In-place so os.walk never descends into what we removed.
        dirnames[:] = sorted(
            d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")
        )
        base = Path(dirpath)
        for name in sorted(filenames):
            visited += 1
            if visited > max_visited:
                return out
            if name.startswith(".") or not is_openable(name):
                continue
            try:
                rel = (base / name).relative_to(root)
            except ValueError:
                continue
            out.append(rel.as_posix())
            if len(out) >= max_files:
                return out
    return out

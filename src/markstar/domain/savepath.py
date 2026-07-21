"""Turn typed path text into a real path.

Relative paths need a base to hang off. The app decides what that base is
(project root → active file's folder → cwd); this module just applies it, so the
rule is testable without an App.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_SUFFIX = ".md"


def resolve_save_path(
    raw: str, base_dir: Path | str, default_suffix: str = DEFAULT_SUFFIX
) -> Path | None:
    """Expand typed text into a path, or None if the text was empty.

    Strips surrounding quotes (paste from a file manager), expands ``~``,
    resolves relative text against ``base_dir``, and gives bare names a default
    extension so "chapter-4" saves as "chapter-4.md". Pass ``default_suffix=""``
    to skip that last step (opening, where a suffixless file is legitimate).
    """
    text = raw.strip().strip('"').strip("'")
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = Path(base_dir) / path
    if default_suffix and path.suffix == "":
        path = path.with_suffix(default_suffix)
    return path

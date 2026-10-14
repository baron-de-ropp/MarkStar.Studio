"""One-level directory listing for the shared file-browser modal.

The modal walks folder-by-folder the way a Works Open dialog does; this module
only answers "what rows should that dialog show for *this* directory?"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from markstar.domain.filewalk import IGNORED_DIRS


@dataclass(frozen=True)
class BrowserEntry:
    """One row in the file browser: name, absolute path, directory flag."""

    name: str
    path: Path
    is_dir: bool
    is_parent: bool = False


def list_browser_entries(
    directory: Path | str,
    *,
    include_parent: bool = False,
) -> list[BrowserEntry]:
    """Children of ``directory``: dirs first, then files, each group A→Z.

    Hidden names and writer-irrelevant dirs (``.git``, ``node_modules``, …) are
    omitted. ``include_parent`` adds a ``..`` row that points at the parent,
    except when ``directory`` is already the filesystem root.
    """
    root = Path(directory).expanduser()
    try:
        root = root.resolve()
    except OSError:
        return []

    out: list[BrowserEntry] = []
    if include_parent:
        parent = root.parent
        if parent != root:
            out.append(BrowserEntry("..", parent, True, is_parent=True))

    dirs: list[BrowserEntry] = []
    files: list[BrowserEntry] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return out

    for child in children:
        name = child.name
        if name.startswith("."):
            continue
        try:
            is_dir = child.is_dir()
        except OSError:
            continue
        if is_dir and name in IGNORED_DIRS:
            continue
        entry = BrowserEntry(name, child, is_dir)
        if is_dir:
            dirs.append(entry)
        else:
            files.append(entry)

    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())
    out.extend(dirs)
    out.extend(files)
    return out

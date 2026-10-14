"""Recent-items bookkeeping — the MRU lists behind the welcome screen.

Pure list algebra plus two display helpers. The app owns persistence (see
``config.Preferences``); this module only decides ordering, staleness, and how a
row reads. Kept out of the UI so the welcome screen stays render-only.
"""

from __future__ import annotations

import time
from pathlib import Path

_MINUTE = 60
_HOUR = 60 * _MINUTE
_DAY = 24 * _HOUR
_WEEK = 7 * _DAY


def push_recent(items: list[str], path: Path | str, cap: int) -> list[str]:
    """Return ``items`` with ``path`` moved to the front, deduped and capped.

    Paths are resolved first so the same file reached by two spellings
    (``./ch1.md`` and an absolute path) collapses to one entry. An unresolvable
    path leaves the list untouched — a bad entry is worse than a missing one.
    """
    try:
        key = str(Path(path).expanduser().resolve())
    except Exception:
        return list(items)
    out = [x for x in items if x != key]
    out.insert(0, key)
    return out[:cap]


def prune_missing(items: list[str]) -> list[str]:
    """Drop entries that are no longer readable files (moved, renamed, deleted)."""
    kept = []
    for x in items:
        try:
            if Path(x).is_file():
                kept.append(x)
        except OSError:
            continue
    return kept


def prune_forbidden_projects(
    items: list[str], *, home: Path | None = None
) -> list[str]:
    """Drop project roots that must never be treated as a manuscript folder.

    ``$HOME`` and ``/`` are useful places to *launch from*, but opening them as
    the project turns the file tree into "everything on the machine."
    """
    home = Path.home() if home is None else home
    try:
        home_key = str(home.expanduser().resolve())
    except OSError:
        home_key = str(home)
    kept: list[str] = []
    for x in items:
        try:
            key = str(Path(x).expanduser().resolve())
        except OSError:
            continue
        if key in (home_key, "/"):
            continue
        kept.append(x)
    return kept


def relative_age(mtime: float, now: float | None = None) -> str:
    """Human-scale age of a timestamp: "3h ago", "2d ago", "Mar 2024"."""
    now = time.time() if now is None else now
    delta = now - mtime
    if delta < 0:
        return "just now"  # clock skew / file from the future
    if delta < _MINUTE:
        return "just now"
    if delta < _HOUR:
        return f"{int(delta // _MINUTE)}m ago"
    if delta < _DAY:
        return f"{int(delta // _HOUR)}h ago"
    if delta < _WEEK:
        return f"{int(delta // _DAY)}d ago"
    if delta < 5 * _WEEK:
        return f"{int(delta // _WEEK)}w ago"
    return time.strftime("%b %Y", time.localtime(mtime))


def abbreviate_dir(directory: Path | str, *, home: Path | None = None, width: int = 34) -> str:
    """Shorten a directory for a one-line list row: ``~``-relative, middle-elided.

    Elision keeps the head and tail (``~/books/…/act-two``) because both ends
    carry identity — the project and the folder you were actually in.
    """
    text = str(directory)
    home = Path.home() if home is None else home
    try:
        text = "~/" + str(Path(directory).relative_to(home))
    except (ValueError, OSError):
        pass
    if len(text) <= width:
        return text
    keep = width - 3  # room for the ellipsis
    head = keep // 2
    tail = keep - head
    return f"{text[:head]}…{text[-tail:]}"

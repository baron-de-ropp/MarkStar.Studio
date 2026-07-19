"""Autosave sidecars: crash-safety without touching the real file.

While a saved file is dirty, MarkStar debounces a write to a hidden sidecar next
to it (``.<name>.autosave``). Explicit Save writes the real file and deletes the
sidecar. On open, if the sidecar is newer than the file, unsaved work survived a
crash and the user is offered Restore / Discard. The original file is only ever
replaced on an explicit Save.
"""

from __future__ import annotations

from pathlib import Path


def sidecar_path(file_path: Path) -> Path:
    """`.<name>.autosave` beside the file (e.g. `.chapter-01.md.autosave`)."""
    return file_path.parent / f".{file_path.name}.autosave"


def write_sidecar(file_path: Path, text: str) -> bool:
    try:
        sidecar_path(file_path).write_text(text, encoding="utf-8")
        return True
    except OSError:
        return False


def read_sidecar(file_path: Path) -> str | None:
    try:
        return sidecar_path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def delete_sidecar(file_path: Path) -> None:
    try:
        sidecar_path(file_path).unlink(missing_ok=True)
    except OSError:
        pass


def sidecar_is_newer(file_path: Path) -> bool:
    """True if a sidecar exists and is newer than the file (unsaved work).

    Treats a sidecar next to a missing file as recoverable too.
    """
    sc = sidecar_path(file_path)
    try:
        if not sc.is_file():
            return False
        if not file_path.exists():
            return True
        return sc.stat().st_mtime > file_path.stat().st_mtime
    except OSError:
        return False

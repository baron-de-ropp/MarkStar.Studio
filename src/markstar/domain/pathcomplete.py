"""Filesystem path completion for the path-entry inputs.

Given a partially-typed path, return the longest unambiguous completion plus the
full list of candidate paths (for Tab-cycling). Deterministic given the
filesystem; cross-platform (uses os.sep / altsep, honors ~ expansion). Directory
matches get a trailing separator so the next Tab descends into them.
"""

from __future__ import annotations

import os


def _split(text: str) -> tuple[str, str, str]:
    """Return (list_dir, partial_basename, original_prefix).

    ``list_dir`` is the directory to scan (expanded), ``partial`` is the basename
    being completed, and ``original_prefix`` is the untouched leading text up to
    the basename (so we can preserve the user's spelling, e.g. a literal ``~/``).
    """
    expanded = os.path.expanduser(text)
    seps = (os.sep,) + ((os.altsep,) if os.altsep else ())
    if text == "" or expanded.endswith(seps):
        list_dir = expanded or "."
        partial = ""
        prefix = text
    else:
        list_dir = os.path.dirname(expanded) or "."
        partial = os.path.basename(expanded)
        prefix = text[: len(text) - len(partial)]
    return list_dir, partial, prefix


def complete_path(text: str) -> tuple[str, list[str]]:
    """Complete ``text`` against the filesystem.

    Returns ``(completion, matches)`` where ``completion`` is the longest common
    prefix shared by every candidate (what a single Tab should fill in) and
    ``matches`` is the full list of candidate paths, in display form (original
    prefix + entry name, directories suffixed with a separator). On no match,
    returns ``(text, [])`` unchanged.
    """
    list_dir, partial, prefix = _split(text)
    try:
        entries = sorted(os.listdir(list_dir or "."))
    except OSError:
        return text, []

    # Hidden entries only surface when the user is explicitly typing a dot.
    show_hidden = partial.startswith(".")
    names = [
        e
        for e in entries
        if e.startswith(partial) and (show_hidden or not e.startswith("."))
    ]
    if not names:
        return text, []

    matches: list[str] = []
    for name in names:
        disp = prefix + name
        if os.path.isdir(os.path.join(list_dir, name)):
            disp += os.sep
        matches.append(disp)

    completion = os.path.commonprefix(matches)
    return completion, matches

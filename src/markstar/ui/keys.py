"""Key-name helpers for terminal quirks."""

from __future__ import annotations

# Canonical modifier order for comparisons (Textual may emit any order).
_MOD_ORDER = ("ctrl", "alt", "shift", "meta", "super", "hyper")


def normalize_key(key: str) -> str:
    """Lowercase letter segments and canonicalize modifier order.

    Some stacks emit ``ctrl+R`` (capital) or ``shift+ctrl+r`` (reordered);
    Textual binding matching is case- and order-sensitive. This makes the
    on_key fallback comparisons robust. (MarkStar's real keymap avoids the
    stacked-modifier chords that made this necessary in the first place; the
    helper stays for defensive matching in ``MarkStarApp.on_key``.)
    """
    if not key:
        return key
    if "+" not in key:
        if len(key) == 1 and key.isalpha():
            return key.lower()
        return key

    parts = key.split("+")
    last = parts[-1]
    if len(last) == 1 and last.isalpha():
        last = last.lower()
        parts = parts[:-1] + [last]

    mods = [p for p in parts[:-1]]
    base = parts[-1]
    known = [m for m in _MOD_ORDER if m in mods]
    unknown = [m for m in mods if m not in _MOD_ORDER]
    ordered = unknown + known + [base]
    return "+".join(ordered)

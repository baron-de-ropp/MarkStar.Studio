"""Key-name helpers for terminal quirks."""

from __future__ import annotations

# Terminals disagree on modifier order for the same physical chord.
_REPLACE_ALL_KEYS = frozenset(
    {
        "ctrl+alt+r",
        "alt+ctrl+r",
    }
)


def normalize_key(key: str) -> str:
    """Lowercase single-letter segments of a key chord.

    With Shift held, many stacks report ``ctrl+shift+H`` (capital letter).
    Textual bindings are case-sensitive, so ``ctrl+shift+h`` never matches.
    """
    if not key or "+" not in key:
        # Bare letter keys: leave as-is (Textual uses "h" / "H" differently).
        if len(key) == 1 and key.isalpha():
            return key.lower()
        return key
    parts = key.split("+")
    last = parts[-1]
    if len(last) == 1 and last.isalpha():
        parts[-1] = last.lower()
        return "+".join(parts)
    return key


def is_replace_all_key(key: str) -> bool:
    """True if this key chord means Replace All."""
    return normalize_key(key) in _REPLACE_ALL_KEYS

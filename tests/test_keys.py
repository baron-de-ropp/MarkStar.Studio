"""Tests for key-name normalization."""

from __future__ import annotations

from prose.ui.keys import normalize_key


def test_normalize_ctrl_shift_letter_case() -> None:
    assert normalize_key("ctrl+shift+H") == "ctrl+shift+h"
    assert normalize_key("ctrl+shift+h") == "ctrl+shift+h"
    assert normalize_key("ctrl+shift+G") == "ctrl+shift+g"
    assert normalize_key("ctrl+R") == "ctrl+r"


def test_normalize_leaves_named_keys() -> None:
    assert normalize_key("shift+enter") == "shift+enter"
    assert normalize_key("ctrl+shift+enter") == "ctrl+shift+enter"
    assert normalize_key("f3") == "f3"
    assert normalize_key("shift+f3") == "shift+f3"

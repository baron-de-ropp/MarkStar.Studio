"""Tests for key-name normalization."""

from __future__ import annotations

from markstar.ui.keys import normalize_key


def test_normalize_ctrl_letter_case() -> None:
    assert normalize_key("ctrl+R") == "ctrl+r"
    assert normalize_key("ctrl+B") == "ctrl+b"
    assert normalize_key("ctrl+shift+H") == "ctrl+shift+h"


def test_normalize_modifier_order() -> None:
    assert normalize_key("shift+ctrl+r") == "ctrl+shift+r"
    assert normalize_key("shift+ctrl+enter") == "ctrl+shift+enter"


def test_normalize_leaves_named_keys() -> None:
    assert normalize_key("ctrl+pagedown") == "ctrl+pagedown"
    assert normalize_key("f3") == "f3"
    assert normalize_key("up") == "up"
    assert normalize_key("ctrl+b") == "ctrl+b"

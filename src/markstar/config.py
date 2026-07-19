"""Persistent user preferences — theme, mouse mode, formatting, soft wrap.

Stored as human-editable TOML at a platform-appropriate path:
  Linux/BSD : $XDG_CONFIG_HOME/markstar/config.toml  (or ~/.config/markstar/)
  macOS     : ~/.config/markstar/config.toml
  Windows   : %APPDATA%\\MarkStar\\config.toml

Set $MARKSTAR_CONFIG to override the path (used by the test suite so tests
never touch a real user config). Preferences never crash the app: any read or
write error falls back to defaults / is silently ignored.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from markstar.ui.themes import DEFAULT_THEME_NAME, THEME_NAMES

MOUSE_CHOICES = ("auto", "on", "off")


def _clamp_int(value, default: int, lo: int, hi: int) -> int:
    """Return value if it's an int within [lo, hi], else the default."""
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(lo, min(hi, value))


def config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "MarkStar"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "markstar"


def config_path() -> Path:
    override = os.environ.get("MARKSTAR_CONFIG")
    return Path(override) if override else config_dir() / "config.toml"


@dataclass
class Preferences:
    """User-facing settings that persist between sessions."""

    theme: str = DEFAULT_THEME_NAME
    mouse: str = "auto"  # auto | on | off
    formatting: bool = True
    soft_wrap: bool = True
    panel_width: int = 40  # project panel columns
    prose_width: int = 120  # max writing-measure columns (line wrap cap)

    @classmethod
    def load(cls) -> "Preferences":
        prefs = cls()
        try:
            with open(config_path(), "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return prefs  # missing / unreadable / malformed → defaults

        theme = data.get("theme")
        if isinstance(theme, str) and theme in THEME_NAMES:
            prefs.theme = theme
        mouse = data.get("mouse")
        if isinstance(mouse, str) and mouse in MOUSE_CHOICES:
            prefs.mouse = mouse
        if isinstance(data.get("formatting"), bool):
            prefs.formatting = data["formatting"]
        if isinstance(data.get("soft_wrap"), bool):
            prefs.soft_wrap = data["soft_wrap"]
        prefs.panel_width = _clamp_int(data.get("panel_width"), prefs.panel_width, 15, 80)
        prefs.prose_width = _clamp_int(data.get("prose_width"), prefs.prose_width, 40, 400)
        return prefs

    def save(self) -> None:
        try:
            path = config_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._to_toml(), encoding="utf-8")
        except OSError:
            pass  # never let a config write take down the editor

    def _to_toml(self) -> str:
        lines = ["# MarkStar preferences — safe to hand-edit.", ""]
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, bool):  # bool before int (bool subclasses int)
                lines.append(f"{f.name} = {str(value).lower()}")
            elif isinstance(value, int):
                lines.append(f"{f.name} = {value}")
            else:
                lines.append(f'{f.name} = "{value}"')
        return "\n".join(lines) + "\n"

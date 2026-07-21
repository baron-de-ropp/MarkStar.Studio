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
from dataclasses import dataclass, field, fields
from pathlib import Path

from markstar.domain.spellcheck import SPELL_LANGUAGES
from markstar.ui.themes import DEFAULT_THEME_NAME, THEME_NAMES

MOUSE_CHOICES = ("auto", "on", "off")

# MRU caps. Projects are a coarse, slow-moving list; files churn fast, so the
# welcome screen's file tab is worth a deeper history.
RECENT_PROJECTS_MAX = 5
RECENT_FILES_MAX = 15


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


def session_path() -> Path:
    """Where the open-tabs session lives (never the preferences file)."""
    override = os.environ.get("MARKSTAR_SESSION")
    return Path(override) if override else config_dir() / "session.toml"


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
    min_panel_width: int = 40  # project panel min columns (grows to fill margin)
    prose_width: int = 120  # max writing-measure columns (line wrap cap)
    center_text: bool = True  # center the prose column in the terminal
    line_numbers: bool = False  # faint left gutter (off: nothing between you and the page)
    spellcheck: bool = True  # underline unknown words
    spellcheck_ms: int = 600  # debounce before re-checking after edits
    spell_language: str = "en"  # bundled dictionary (see SPELL_LANGUAGES)
    autosave: bool = True  # debounced crash-safety sidecars
    autosave_ms: int = 1500  # debounce delay
    restore_session: bool = True  # offer to reopen last session on the splash
    recent_projects: list = field(default_factory=list)  # last folders (max 5)
    recent_files: list = field(default_factory=list)  # last documents (max 15)
    spell_added: list = field(default_factory=list)  # personal dictionary

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
        if isinstance(data.get("center_text"), bool):
            prefs.center_text = data["center_text"]
        if isinstance(data.get("line_numbers"), bool):
            prefs.line_numbers = data["line_numbers"]
        if isinstance(data.get("spellcheck"), bool):
            prefs.spellcheck = data["spellcheck"]
        lang = data.get("spell_language")
        if isinstance(lang, str) and lang in SPELL_LANGUAGES:
            prefs.spell_language = lang
        if isinstance(data.get("autosave"), bool):
            prefs.autosave = data["autosave"]
        if isinstance(data.get("restore_session"), bool):
            prefs.restore_session = data["restore_session"]
        rp = data.get("recent_projects")
        if isinstance(rp, list):
            prefs.recent_projects = [
                str(x) for x in rp if isinstance(x, str)
            ][:RECENT_PROJECTS_MAX]
        rf = data.get("recent_files")
        if isinstance(rf, list):
            prefs.recent_files = [
                str(x) for x in rf if isinstance(x, str)
            ][:RECENT_FILES_MAX]
        sa = data.get("spell_added")
        if isinstance(sa, list):
            prefs.spell_added = [str(x) for x in sa if isinstance(x, str)]
        prefs.min_panel_width = _clamp_int(
            data.get("min_panel_width"), prefs.min_panel_width, 15, 80
        )
        prefs.prose_width = _clamp_int(data.get("prose_width"), prefs.prose_width, 40, 400)
        prefs.autosave_ms = _clamp_int(
            data.get("autosave_ms"), prefs.autosave_ms, 100, 60000
        )
        prefs.spellcheck_ms = _clamp_int(
            data.get("spellcheck_ms"), prefs.spellcheck_ms, 100, 10000
        )
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
            elif isinstance(value, list):
                items = ", ".join('"' + str(v).replace('"', '\\"') + '"' for v in value)
                lines.append(f"{f.name} = [{items}]")
            else:
                lines.append(f'{f.name} = "{value}"')
        return "\n".join(lines) + "\n"

"""The help screen (F1) — every command, read from the command registry.

Generated rather than written, so it cannot drift the way the hand-maintained
key tables in the docs did. If a command exists, it is in here; if its key
changes, this changes with it.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from markstar.ui.themes import token

# Keys that belong to a focused context rather than to a menu command, so the
# registry doesn't know about them.
_CONTEXT_KEYS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "While the find bar is open",
        [
            ("Enter", "Next match (or replace one, in the replace field)"),
            ("↑ ↓", "Previous / next match"),
            ("Ctrl+R", "Expand find into replace"),
            ("Ctrl+L", "Replace all"),
            ("Ctrl+T", "Toggle match case"),
            ("Esc", "Close the find bar"),
        ],
    ),
    (
        "While the project panel has focus",
        [
            ("Ctrl+F", "Find / replace across the whole project (same as F8)"),
            ("Ctrl+P", "Back to the editor"),
            ("Enter", "Open the selected file"),
        ],
    ),
    (
        "Project find / replace",
        [
            ("F8", "Find / Replace in Project…"),
            ("Enter", "Run find (from the project find modal)"),
            ("Ctrl+L", "Replace all in project (from the modal)"),
        ],
    ),
    (
        "Moving around",
        [
            ("Ctrl+Home / Ctrl+End", "Start / end of the document"),
            ("Ctrl+← / Ctrl+→", "Word left / right"),
            ("Ctrl+↑ / Ctrl+↓", "Paragraph up / down"),
            ("PageUp / PageDown", "A screen at a time"),
            ("F6 / Shift+F6", "Next / previous tab"),
        ],
    ),
]

# Textual's TextArea binds these; MarkStar reuses the keys for its own commands,
# so the editing commands they used to perform are gone. Documented rather than
# rehomed — the trades are deliberate.
_SHADOWED = [
    ("Ctrl+W", "was delete-word-left", "now Close tab"),
    ("Ctrl+K", "was delete-to-end-of-line", "now StarBot panel"),
    ("Ctrl+E", "was cursor-to-line-end", "now Italic"),
]


class HelpScreen(ModalScreen[None]):
    """Scrollable keyboard reference. Esc closes."""

    CSS = """
    HelpScreen { align: center middle; background: rgba(0,0,0,0.6); }
    #help-panel {
        width: 84; max-width: 94%; height: 84%;
        background: $boost; border: tall $accent; padding: 1 2;
    }
    #help-title { text-style: bold; color: $text; padding-bottom: 1; }
    #help-body { height: 1fr; }
    .help-heading { text-style: bold; color: $text; padding: 1 0 0 0; }
    .help-row { color: $text-muted; }
    #help-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "close", show=False, priority=True),
        Binding("f1", "close", show=False, priority=True),
    ]

    def __init__(self, registry, version: str = "") -> None:
        super().__init__()
        self._registry = registry
        self._version = version

    def _row(self, key: str, label: str) -> Static:
        hk = token(self.app, "hint-key")
        shown = f"[{hk}]{key}[/]" if key else "  "
        pad = max(0, 22 - len(key))
        return Static(f"  {shown}{' ' * pad}{label}", classes="help-row", markup=True)

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        dim = token(self, "rule")
        with Vertical(id="help-panel"):
            yield Label(
                f"MarkStar — keyboard reference{f'  ·  v{self._version}' if self._version else ''}",
                id="help-title",
            )
            with VerticalScroll(id="help-body"):
                # Commands, grouped exactly as the menus present them.
                grouped = self._registry.menus()
                for menu in self._registry.menu_names():
                    commands = grouped.get(menu, [])
                    keyed = [c for c in commands if c.binding]
                    unkeyed = [c for c in commands if not c.binding]
                    if not keyed and not unkeyed:
                        continue
                    yield Static(menu, classes="help-heading")
                    for cmd in keyed:
                        yield self._row(self._pretty(cmd.binding), cmd.label)
                    if unkeyed:
                        names = " · ".join(c.label for c in unkeyed)
                        yield Static(
                            f"  [{dim}]menu only: {names}[/]",
                            classes="help-row",
                            markup=True,
                        )


                for heading, rows in _CONTEXT_KEYS:
                    yield Static(heading, classes="help-heading")
                    for key, label in rows:
                        yield self._row(key, label)

                yield Static("Keys MarkStar took over", classes="help-heading")
                for key, was, now in _SHADOWED:
                    yield self._row(key, f"{now} — {was} in a plain text area")

            yield Label(f"[{hk}]Esc[/] close", id="help-hint")

    @staticmethod
    def _pretty(binding: str) -> str:
        """'ctrl+pagedown' → 'Ctrl+PageDown'."""
        special = {
            "pagedown": "PageDown",
            "pageup": "PageUp",
            "home": "Home",
            "end": "End",
            "escape": "Esc",
            "enter": "Enter",
        }
        parts = []
        for part in binding.split("+"):
            if part in special:
                parts.append(special[part])
            elif len(part) == 1 or part.startswith("f") and part[1:].isdigit():
                parts.append(part.upper())
            else:
                parts.append(part.capitalize())
        return "+".join(parts)

    def action_close(self) -> None:
        self.dismiss(None)

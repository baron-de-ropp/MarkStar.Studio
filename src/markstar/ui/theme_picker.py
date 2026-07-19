"""Theme picker — a centered list that previews themes live as you arrow.

Highlighting a theme applies it immediately (preview); Enter keeps it, Esc
reverts to the theme that was active when the picker opened. The app supplies
the apply/revert callbacks (it owns the repaint).
"""

from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from markstar.ui.themes import token


class ThemePicker(ModalScreen[str]):
    """Pick a theme with live preview."""

    CSS = """
    ThemePicker {
        align: center middle;
        background: rgba(0, 0, 0, 0.45);
    }
    #theme-panel {
        width: 42;
        max-width: 90%;
        height: auto;
        background: $surface;
        border: round $accent;
        padding: 1 2;
    }
    #theme-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }
    #theme-list {
        width: 100%;
        max-height: 12;
        border: none;
        background: $surface;
    }
    #theme-list > .option-list--option-highlighted {
        background: $accent 55%;
        color: $text;
    }
    #theme-hint {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
    ]

    def __init__(
        self,
        names: list[str],
        current: str,
        preview: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._names = names
        self._current = current
        self._preview = preview

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-panel"):
            yield Static("Theme", id="theme-title")
            options = [Option(self._label(n), id=n) for n in self._names]
            yield OptionList(*options, id="theme-list")
            hk = token(self.app, "hint-key")
            yield Static(
                f"[{hk}]↑↓[/] preview   [{hk}]Enter[/] keep   [{hk}]Esc[/] revert",
                id="theme-hint",
            )

    @staticmethod
    def _label(name: str) -> str:
        return name.replace("-", " ").title()

    def on_mount(self) -> None:
        ol = self.query_one("#theme-list", OptionList)
        if self._current in self._names:
            ol.highlighted = self._names.index(self._current)
        ol.focus()

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if event.option is not None and event.option.id:
            self._preview(event.option.id)  # live preview

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()
        self.dismiss(str(event.option.id) if event.option.id else self._current)

    def action_cancel(self) -> None:
        self.dismiss("")  # empty → app reverts to the original theme

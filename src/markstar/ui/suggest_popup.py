"""Suggestion popup — a small list that pops out at a misspelled word.

Anchored at a screen offset (the caret position). Selecting a suggestion
returns it; Esc / clicking away cancels. The app replaces the word.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class SuggestPopup(ModalScreen[str]):
    """Floating suggestion list anchored near the caret."""

    CSS = """
    SuggestPopup {
        align: left top;
        background: transparent;
    }
    SuggestPopup #suggest-list {
        width: auto;
        min-width: 18;
        max-width: 40;
        height: auto;
        max-height: 12;
        border: round $accent;
        background: $surface;
        color: $text;
    }
    SuggestPopup #suggest-list > .option-list--option-highlighted {
        background: $accent 55%;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
    ]

    def __init__(self, word: str, suggestions: list[str], offset: tuple[int, int]) -> None:
        super().__init__()
        self._word = word
        self._suggestions = suggestions
        self._offset = offset

    def compose(self) -> ComposeResult:
        options = [Option(s, id=s) for s in self._suggestions]
        if not options:
            options = [Option("(no suggestions)", disabled=True)]
        yield OptionList(*options, id="suggest-list")

    def on_mount(self) -> None:
        ol = self.query_one("#suggest-list", OptionList)
        ol.styles.offset = self._offset
        ol.focus()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()
        self.dismiss(str(event.option.id) if event.option.id else "")

    def on_click(self, event) -> None:
        # A click that reaches the transparent backdrop (not the list) cancels.
        self.dismiss("")

    def action_cancel(self) -> None:
        self.dismiss("")

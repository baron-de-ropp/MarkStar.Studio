"""Outline overlay (F4) — jump to any heading in the document.

Same shape as Quick Open on purpose: a list you can type to filter and arrow
through. One interaction pattern, learned once.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

from markstar.domain.fuzzy import rank
from markstar.domain.outline import Heading
from markstar.ui.themes import token


class OutlineScreen(ModalScreen[int | None]):
    """Dismisses with the chosen heading's line index, or None."""

    CSS = """
    OutlineScreen { align: center middle; background: rgba(0,0,0,0.55); }
    #outline-panel {
        width: 72; max-width: 92%; height: auto; max-height: 80%;
        background: $boost; border: tall $accent; padding: 1 2;
    }
    #outline-title { text-style: bold; color: $text; padding-bottom: 1; }
    #outline-input { width: 100%; }
    #outline-list {
        height: auto; max-height: 16; background: $boost; border: none;
        padding: 1 0 0 0;
    }
    #outline-list > .option-list--option-highlighted {
        background: $accent 45%; color: $text;
    }
    #outline-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("enter", "submit", show=False, priority=True),
    ]

    def __init__(self, headings: list[Heading], current_line: int = 0) -> None:
        super().__init__()
        self._headings = headings
        self._current_line = current_line
        self._rows: list[Heading] = []

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        with Vertical(id="outline-panel"):
            yield Label("Outline — jump to a heading", id="outline-title")
            yield Input(placeholder="type to filter…", id="outline-input")
            yield OptionList(id="outline-list")
            yield Label(
                f"[{hk}]↑↓[/] choose  ·  [{hk}]Enter[/] jump  ·  [{hk}]Esc[/] cancel",
                id="outline-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#outline-input", Input).focus()
        self._populate("")

    def _label(self, h: Heading) -> str:
        dim = token(self, "rule")
        indent = "  " * (h.level - 1)
        return f"{indent}{h.text}   [{dim}]l.{h.line + 1}[/]"

    def _populate(self, query: str) -> None:
        try:
            ol = self.query_one("#outline-list", OptionList)
        except Exception:
            return
        ol.clear_options()
        if not self._headings:
            self._rows = []
            ol.add_option(Option("No headings in this document", disabled=True))
            return
        if query:
            wanted = set(rank(query, [h.text for h in self._headings], limit=200))
            self._rows = [h for h in self._headings if h.text in wanted]
        else:
            self._rows = list(self._headings)
        if not self._rows:
            ol.add_option(Option("no matches", disabled=True))
            return
        ol.add_options([Option(self._label(h)) for h in self._rows])
        # Land on the section the caret is already in, so opening the outline
        # from mid-chapter starts there rather than at the top of the book.
        start = 0
        for i, h in enumerate(self._rows):
            if h.line <= self._current_line:
                start = i
            else:
                break
        ol.highlighted = start

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._populate(event.value)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("up", "down"):
            event.prevent_default()
            event.stop()
            ol = self.query_one("#outline-list", OptionList)
            ol.action_cursor_up() if event.key == "up" else ol.action_cursor_down()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._submit(event.option_index)

    def action_submit(self) -> None:
        self._submit(self.query_one("#outline-list", OptionList).highlighted)

    def _submit(self, index: int | None) -> None:
        if index is None or index >= len(self._rows):
            return
        self.dismiss(self._rows[index].line)

    def action_cancel(self) -> None:
        self.dismiss(None)

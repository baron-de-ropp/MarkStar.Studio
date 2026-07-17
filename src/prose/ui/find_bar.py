"""Find / replace bar docked at the top of the prose frame."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Label, Static


class FindBar(Static):
    """Top-of-editor find UI. Enter = next, Shift+Enter = prev."""

    DEFAULT_CSS = """
    FindBar {
        height: auto;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $accent 40%;
        display: none;
    }

    FindBar.visible {
        display: block;
    }

    FindBar Input {
        width: 1fr;
    }

    FindBar #find-label, FindBar #replace-label {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("enter", "find_next", "Next", show=False),
        Binding("shift+enter", "find_prev", "Prev", show=False),
    ]

    class Submitted(Message):
        def __init__(self, direction: str) -> None:
            super().__init__()
            self.direction = direction  # "next" | "prev"

    class Dismissed(Message):
        pass

    class ReplaceRequested(Message):
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode  # "one" | "all"

    def __init__(self, *args, show_replace: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._show_replace = show_replace

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label("Find", id="find-label")
            yield Input(placeholder="Find…", id="find-input")
        with Horizontal(id="replace-row"):
            yield Label("Replace", id="replace-label")
            yield Input(placeholder="Replace with…", id="replace-input")

    def on_mount(self) -> None:
        self._apply_replace_visibility()

    def show(self, *, replace: bool = False) -> None:
        self._show_replace = replace
        self._apply_replace_visibility()
        self.add_class("visible")
        self.query_one("#find-input", Input).focus()

    def hide(self) -> None:
        self.remove_class("visible")
        self.post_message(self.Dismissed())

    @property
    def query(self) -> str:
        return self.query_one("#find-input", Input).value

    @property
    def replacement(self) -> str:
        return self.query_one("#replace-input", Input).value

    def action_dismiss(self) -> None:
        self.hide()

    def action_find_next(self) -> None:
        self.post_message(self.Submitted("next"))

    def action_find_prev(self) -> None:
        self.post_message(self.Submitted("prev"))

    def _apply_replace_visibility(self) -> None:
        row = self.query_one("#replace-row", Horizontal)
        row.display = self._show_replace

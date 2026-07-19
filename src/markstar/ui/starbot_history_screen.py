"""A picker for past StarBot conversations (Project → StarBot History…)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from markstar.ui.themes import token


class ChatHistoryScreen(ModalScreen[str]):
    """Lists saved transcripts; dismisses with the chosen id (or '')."""

    CSS = """
    ChatHistoryScreen { align: center middle; background: rgba(0,0,0,0.55); }
    #hist-panel {
        width: 78; max-width: 92%; height: auto; max-height: 80%;
        background: $boost; border: tall $accent; padding: 1 2;
    }
    #hist-title { text-style: bold; color: $text; padding-bottom: 1; }
    #hist-list { height: auto; max-height: 20; background: $boost; border: none; }
    #hist-list > .option-list--option-highlighted {
        background: $accent 45%; color: $text;
    }
    #hist-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [Binding("escape", "cancel", "Close", show=False, priority=True)]

    def __init__(self, transcripts) -> None:
        super().__init__()
        self._transcripts = transcripts

    def compose(self) -> ComposeResult:
        dim = token(self, "rule")
        with Vertical(id="hist-panel"):
            yield Label("StarBot — past chats", id="hist-title")
            options = []
            for t in self._transcripts:
                date = t.created.replace("T", " ")[:16] or t.id
                turns = f"{t.turn_count} turn{'s' if t.turn_count != 1 else ''}"
                options.append(
                    Option(f"{t.title}   [{dim}]{date} · {turns}[/]", id=t.id)
                )
            yield OptionList(*options, id="hist-list")
            yield Label("Enter open · Esc cancel", id="hist-hint")

    def on_mount(self) -> None:
        self.query_one("#hist-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(str(event.option.id) if event.option.id else "")

    def action_cancel(self) -> None:
        self.dismiss("")

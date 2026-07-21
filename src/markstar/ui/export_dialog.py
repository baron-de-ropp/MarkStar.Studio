"""Pick an export format. Unavailable formats stay visible, with the reason.

Hiding DOCX because pandoc is missing would leave the writer wondering whether
MarkStar can export to Word at all. Showing it greyed, with "needs pandoc",
answers the question and says what to do about it.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from markstar.domain.export import Format, available_formats
from markstar.ui.themes import token


class ExportDialog(ModalScreen[Format | None]):
    """Dismisses with the chosen Format, or None on cancel."""

    CSS = """
    ExportDialog { align: center middle; background: rgba(0,0,0,0.55); }
    #export-panel {
        width: 62; max-width: 92%; height: auto;
        background: $boost; border: tall $accent; padding: 1 2;
    }
    #export-title { text-style: bold; color: $text; padding-bottom: 1; }
    #export-list { height: auto; background: $boost; border: none; }
    #export-list > .option-list--option-highlighted {
        background: $accent 45%; color: $text;
    }
    #export-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [Binding("escape", "cancel", show=False, priority=True)]

    def __init__(self) -> None:
        super().__init__()
        self._formats = available_formats()

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        dim = token(self, "rule")
        with Vertical(id="export-panel"):
            yield Label("Export — choose a format", id="export-title")
            options = []
            for i, f in enumerate(self._formats):
                if f.available:
                    options.append(Option(f.label, id=str(i)))
                else:
                    options.append(
                        Option(f"{f.label}   [{dim}]· {f.reason}[/]", disabled=True)
                    )
            yield OptionList(*options, id="export-list")
            yield Label(
                f"[{hk}]↑↓[/] choose  ·  [{hk}]Enter[/] export  ·  [{hk}]Esc[/] cancel",
                id="export-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#export-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option.id is not None:
            self.dismiss(self._formats[int(event.option.id)])

    def action_cancel(self) -> None:
        self.dismiss(None)

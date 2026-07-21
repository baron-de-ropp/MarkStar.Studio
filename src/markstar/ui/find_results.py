"""Project-wide find results — every hit, grouped by file, Enter to open there."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from markstar.domain.projectsearch import Hit, Results
from markstar.ui.themes import token


class FindResultsScreen(ModalScreen[Hit | None]):
    """Dismisses with the chosen Hit, or None."""

    CSS = """
    FindResultsScreen { align: center middle; background: rgba(0,0,0,0.55); }
    #results-panel {
        width: 86; max-width: 94%; height: auto; max-height: 82%;
        background: $boost; border: tall $accent; padding: 1 2;
    }
    #results-title { text-style: bold; color: $text; padding-bottom: 1; }
    #results-list {
        height: auto; max-height: 18; background: $boost; border: none;
    }
    #results-list > .option-list--option-highlighted {
        background: $accent 45%; color: $text;
    }
    #results-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [Binding("escape", "cancel", show=False, priority=True)]

    def __init__(self, query: str, results: Results) -> None:
        super().__init__()
        self._query = query
        self._results = results
        self._rows: list[Hit] = []

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        dim = token(self, "rule")
        n = len(self._results.hits)
        files = len({h.relative for h in self._results.hits})
        headline = (
            f'{n} hit{"s" if n != 1 else ""} for "{self._query}" '
            f'in {files} file{"s" if files != 1 else ""}'
            if n
            else f'No hits for "{self._query}"'
        )
        if self._results.truncated:
            # Say so: a capped list that looks complete is worse than no list.
            headline += "  (stopped at the limit — narrow the search)"
        with Vertical(id="results-panel"):
            yield Label(headline, id="results-title")
            options = []
            last_file = None
            for i, hit in enumerate(self._results.hits):
                if hit.relative != last_file:
                    options.append(Option(f"[{dim}]{hit.relative}[/]", disabled=True))
                    last_file = hit.relative
                self._rows.append(hit)
                options.append(
                    Option(f"  [{dim}]{hit.line + 1:>5}[/]  {hit.preview}", id=str(i))
                )
            yield OptionList(*options, id="results-list")
            yield Label(
                f"[{hk}]↑↓[/] choose  ·  [{hk}]Enter[/] open  ·  [{hk}]Esc[/] close",
                id="results-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#results-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option.id is not None:
            self.dismiss(self._results.hits[int(event.option.id)])

    def action_cancel(self) -> None:
        self.dismiss(None)

"""Quick Open (Ctrl+O) — type a few letters, get the file.

Two modes in one field. Normally it fuzzy-matches recent files and everything
openable under the project root. Start the line with ``/``, ``~``, ``./`` or
``../`` and it becomes a literal path field with Tab completion — the escape
hatch for files outside the project.

Dismisses with the chosen Path, or None on cancel.
"""

from __future__ import annotations

from pathlib import Path

from textual import events, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

from markstar.domain.filewalk import list_project_files
from markstar.domain.fuzzy import rank
from markstar.domain.recent import abbreviate_dir
from markstar.ui.path_input import CompletionCycler
from markstar.ui.themes import token

# Prefixes that switch the field from fuzzy matching to literal path entry.
_LITERAL_PREFIXES = ("/", "~", "./", "../", "..\\", ".\\")

_MAX_ROWS = 40


class QuickOpenScreen(ModalScreen[Path | None]):
    """Fuzzy file picker over recents + the project tree."""

    CSS = """
    QuickOpenScreen { align: center middle; background: rgba(0,0,0,0.55); }
    #qo-panel {
        width: 78; max-width: 92%; height: auto; max-height: 80%;
        background: $boost; border: tall $accent; padding: 1 2;
    }
    #qo-title { text-style: bold; color: $text; padding-bottom: 1; }
    #qo-input { width: 100%; }
    #qo-list {
        height: auto; max-height: 14; background: $boost; border: none;
        padding: 1 0 0 0;
    }
    #qo-list > .option-list--option-highlighted {
        background: $accent 45%; color: $text;
    }
    #qo-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("enter", "submit", show=False, priority=True),
    ]

    def __init__(self, recents: list[str], root: Path | None) -> None:
        super().__init__()
        self._recents = list(recents)
        self._root = root
        # Project files arrive from a thread worker; recents are usable at once.
        self._project: list[str] = []
        self._cycler = CompletionCycler()
        self._rows: list[str] = []  # candidate strings parallel to the option list

    # ---- composition -----------------------------------------------------

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        with Vertical(id="qo-panel"):
            yield Label("Open — type to search", id="qo-title")
            yield Input(placeholder="file name…", id="qo-input")
            yield OptionList(id="qo-list")
            yield Label(
                f"[{hk}]↑↓[/] choose  ·  [{hk}]Enter[/] open  ·  "
                f"[{hk}]Esc[/] cancel  ·  start with [{hk}]/[/] [{hk}]~[/] [{hk}]./[/] "
                "for a path",
                id="qo-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#qo-input", Input).focus()
        self._populate("")
        if self._root is not None:
            self._scan_project(self._root)

    @work(thread=True, exit_on_error=False)
    def _scan_project(self, root: Path) -> None:
        """Walk the project off the UI thread; recents stay usable meanwhile."""
        files = list_project_files(root)
        self.app.call_from_thread(self._project_ready, files)

    def _project_ready(self, files: list[str]) -> None:
        self._project = files
        try:
            value = self.query_one("#qo-input", Input).value
        except Exception:
            return
        if not self._is_literal(value):
            self._populate(value)

    # ---- candidates + rendering -----------------------------------------

    @staticmethod
    def _is_literal(value: str) -> bool:
        return value.startswith(_LITERAL_PREFIXES)

    def _candidates(self) -> list[str]:
        """Recents (absolute) first, then project files (root-relative)."""
        seen = set(self._recents)
        rel_root = self._root
        project = []
        for rel in self._project:
            if rel_root is not None and str((rel_root / rel).resolve()) in seen:
                continue  # already listed as a recent
            project.append(rel)
        return self._recents + project

    def _row_label(self, cand: str) -> str:
        dim = token(self, "rule")
        path = Path(cand)
        if cand in self._recents:
            return f"{path.name}   [{dim}]{abbreviate_dir(path.parent)}[/]"
        parent = str(path.parent)
        if parent in (".", ""):
            return path.name
        return f"{path.name}   [{dim}]{parent}[/]"

    def _populate(self, query: str) -> None:
        try:
            ol = self.query_one("#qo-list", OptionList)
        except Exception:
            return
        ol.clear_options()
        if self._is_literal(query):
            self._rows = []
            ol.add_option(Option("path mode — Tab completes", disabled=True))
            return
        self._rows = rank(
            query, self._candidates(), limit=_MAX_ROWS, boost=set(self._recents)
        )
        if not self._rows:
            ol.add_option(Option("no matches", disabled=True))
            return
        ol.add_options([Option(self._row_label(c)) for c in self._rows])
        ol.highlighted = 0

    def _resolve(self, cand: str) -> Path:
        """Row string → real path (recents are absolute, project rows relative)."""
        path = Path(cand)
        if not path.is_absolute() and self._root is not None:
            return self._root / path
        return path

    # ---- input handling --------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._cycler.reset()
        self._populate(event.value)

    def on_key(self, event: events.Key) -> None:
        # The input keeps focus; arrows drive the list underneath it.
        if event.key in ("up", "down"):
            event.prevent_default()
            event.stop()
            ol = self.query_one("#qo-list", OptionList)
            if event.key == "up":
                ol.action_cursor_up()
            else:
                ol.action_cursor_down()
            return
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            inp = self.query_one("#qo-input", Input)
            if not self._is_literal(inp.value):
                return  # fuzzy mode: nothing to complete
            completed = self._cycler.advance(inp.value)
            if completed is not None:
                inp.value = completed
                inp.cursor_position = len(completed)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._submit_index(event.option_index)

    def action_submit(self) -> None:
        inp = self.query_one("#qo-input", Input)
        if self._is_literal(inp.value):
            text = inp.value.strip().strip('"').strip("'")
            if not text:
                self.dismiss(None)
                return
            self.dismiss(Path(text).expanduser())
            return
        ol = self.query_one("#qo-list", OptionList)
        self._submit_index(ol.highlighted)

    def _submit_index(self, index: int | None) -> None:
        if index is None or index >= len(self._rows):
            return
        self.dismiss(self._resolve(self._rows[index]))

    def action_cancel(self) -> None:
        self.dismiss(None)

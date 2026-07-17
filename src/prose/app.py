"""Prose TUI entrypoint (P0: buffer shell)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Static, TextArea

from prose import __version__
from prose.domain.document import Document


class ProseApp(App[None]):
    """Minimal writing shell: soft-wrapped editor + word count."""

    TITLE = "Prose"
    CSS = """
    Screen {
        layout: vertical;
    }

    #editor {
        height: 1fr;
        border: tall $accent 40%;
        margin: 1 2;
        padding: 0 1;
    }

    #status {
        height: 1;
        dock: bottom;
        padding: 0 2;
        color: $text-muted;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("ctrl+o", "open_file", "Open", show=True),
        Binding("ctrl+z", "undo", "Undo", show=True),
        Binding("ctrl+shift+z", "redo", "Redo", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self._path_arg = path
        self.document = Document()
        self._syncing = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield TextArea(id="editor")
            yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        editor = self.query_one("#editor", TextArea)
        # Soft wrap for prose (Textual TextArea)
        editor.soft_wrap = True
        editor.show_line_numbers = False

        if self._path_arg is not None and self._path_arg.exists():
            self.document = Document.load(self._path_arg)
            self._syncing = True
            editor.load_text(self.document.text)
            self._syncing = False
            self.title = f"Prose — {self._path_arg.name}"
        else:
            if self._path_arg is not None:
                self.document.path = self._path_arg
                self.title = f"Prose — {self._path_arg.name}"
            editor.focus()

        self._refresh_status()

    @on(TextArea.Changed)
    def _on_editor_changed(self, event: TextArea.Changed) -> None:
        if self._syncing:
            return
        # Push full-buffer replace for P0 (simple; op-based coalescing later)
        new_text = event.text_area.text
        if new_text == self.document.text:
            return
        self.document.set_text(new_text)
        self._refresh_status()

    def _refresh_status(self) -> None:
        status = self.query_one("#status", Static)
        name = self.document.path.name if self.document.path else "Untitled"
        dirty = " •" if self.document.dirty else ""
        words = self.document.word_count()
        status.update(
            f"{name}{dirty}  │  {words} words  │  "
            f"CommonMark  │  ^S save  ^Z undo  ^⇧Z redo  ^Q quit"
        )
        if self.document.path:
            self.title = f"Prose — {self.document.path.name}{dirty}"

    def action_save(self) -> None:
        editor = self.query_one("#editor", TextArea)
        # Ensure document matches editor before save
        if editor.text != self.document.text:
            self.document.set_text(editor.text)

        if self.document.path is None:
            self.notify("No path yet — open with: prose path/to/file.md", severity="warning")
            return
        try:
            self.document.save()
            self.notify(f"Saved {self.document.path}")
            self._refresh_status()
        except OSError as exc:
            self.notify(f"Save failed: {exc}", severity="error")

    def action_open_file(self) -> None:
        self.notify("P0: open a file from the CLI — prose path/to/file.md", severity="information")

    def action_undo(self) -> None:
        if not self.document.undo():
            return
        self._push_document_to_editor()
        self._refresh_status()

    def action_redo(self) -> None:
        if not self.document.redo():
            return
        self._push_document_to_editor()
        self._refresh_status()

    def _push_document_to_editor(self) -> None:
        editor = self.query_one("#editor", TextArea)
        self._syncing = True
        editor.load_text(self.document.text)
        self._syncing = False


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="prose", description="Prose — terminal Markdown word processor")
    parser.add_argument("path", nargs="?", type=Path, help="Markdown file to open")
    parser.add_argument("--version", action="version", version=f"Prose {__version__}")
    args = parser.parse_args(argv)

    app = ProseApp(path=args.path)
    app.run()


if __name__ == "__main__":
    main(sys.argv[1:])

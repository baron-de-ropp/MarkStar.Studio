"""Modal dialogs — path entry, yes/no confirm, autosave restore.

Extracted from app.py. Each is a small ``ModalScreen`` returning a typed result
via ``dismiss`` (consumed with ``push_screen_wait``).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from markstar.ui.path_input import PathInput
from markstar.ui.themes import token


class PathPrompt(ModalScreen[str | None]):
    """Modal path entry for Save / Save As. Dismisses with the path or None."""

    CSS = """
    PathPrompt {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #path-panel {
        width: 72;
        max-width: 90%;
        height: auto;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #path-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }
    #path-hint {
        color: $text-muted;
        padding-top: 1;
    }
    #path-input {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("enter", "submit", show=False, priority=True),
    ]

    def __init__(self, title: str, *, initial: str = "", hint: str = "") -> None:
        super().__init__()
        self._title = title
        self._initial = initial
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(id="path-panel"):
            yield Label(self._title, id="path-title")
            yield PathInput(
                value=self._initial, placeholder="/path/to/file.md", id="path-input"
            )
            yield Label(
                self._hint or "Tab · complete   Enter · save   Esc · cancel",
                id="path-hint",
            )

    def on_mount(self) -> None:
        inp = self.query_one("#path-input", Input)
        inp.focus()
        # Park the caret at the end so typing appends to the default name.
        if self._initial:
            try:
                inp.cursor_position = len(self._initial)
            except Exception:
                pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#path-input", Input).value)


class ConfirmDialog(ModalScreen[bool]):
    """Yes/No confirm. True = yes, False = no/cancel."""

    CSS = """
    ConfirmDialog {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #confirm-panel {
        width: 64;
        max-width: 90%;
        height: auto;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #confirm-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }
    #confirm-message {
        color: $text-muted;
        padding-bottom: 1;
    }
    #confirm-hint {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("n", "cancel", show=False, priority=True),
        Binding("enter", "confirm", show=False, priority=True),
        Binding("y", "confirm", show=False, priority=True),
    ]

    def __init__(
        self,
        *,
        title: str,
        message: str,
        yes_label: str = "yes",
        no_label: str = "no",
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._yes_label = yes_label
        self._no_label = no_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-panel"):
            yield Label(self._title, id="confirm-title")
            yield Label(self._message, id="confirm-message")
            hk = token(self.app, "hint-key")
            yield Label(
                f"[{hk}]Y[/]/Enter {self._yes_label}  ·  "
                f"[{hk}]N[/]/Esc {self._no_label}",
                id="confirm-hint",
            )

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


class SaveChangesDialog(ModalScreen[str]):
    """Works-style close guard: "Save changes to X?" — Save / Don't Save / Cancel.

    Dismisses with "save", "discard", "save_all", or "cancel". Enter is Save
    because the safe answer should be the reflex one. ``show_save_all`` adds the
    A option, used when a quit is walking several dirty buffers.
    """

    CSS = """
    SaveChangesDialog {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #savechanges-panel {
        width: 66;
        max-width: 90%;
        height: auto;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #savechanges-title { text-style: bold; color: $text; padding-bottom: 1; }
    #savechanges-hint { color: $text-muted; }
    """

    BINDINGS = [
        Binding("enter", "save", show=False, priority=True),
        Binding("s", "save", show=False, priority=True),
        Binding("d", "discard", show=False, priority=True),
        Binding("a", "save_all", show=False, priority=True),
        Binding("escape", "cancel", show=False, priority=True),
    ]

    def __init__(self, name: str, *, show_save_all: bool = False) -> None:
        super().__init__()
        self._name = name
        self._show_save_all = show_save_all

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        with Vertical(id="savechanges-panel"):
            yield Label(f'Save changes to "{self._name}"?', id="savechanges-title")
            hints = [
                f"[{hk}]Enter[/]/[{hk}]S[/] save",
                f"[{hk}]D[/] don't save",
            ]
            if self._show_save_all:
                hints.append(f"[{hk}]A[/] save all")
            hints.append(f"[{hk}]Esc[/] cancel")
            yield Label("  ·  ".join(hints), id="savechanges-hint")

    def action_save(self) -> None:
        self.dismiss("save")

    def action_discard(self) -> None:
        self.dismiss("discard")

    def action_save_all(self) -> None:
        # Ignored unless offered, so a stray A can't silently save everything.
        if self._show_save_all:
            self.dismiss("save_all")

    def action_cancel(self) -> None:
        self.dismiss("cancel")


class RestoreDialog(ModalScreen[str]):
    """Recover unsaved autosave work: Restore / Discard (Esc = decide later)."""

    CSS = """
    RestoreDialog {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #restore-panel {
        width: 66;
        max-width: 90%;
        height: auto;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #restore-title { text-style: bold; color: $text; padding-bottom: 1; }
    #restore-message { color: $text-muted; padding-bottom: 1; }
    #restore-hint { color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "later", show=False, priority=True),
        Binding("r", "restore", show=False, priority=True),
        Binding("d", "discard", show=False, priority=True),
    ]

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        with Vertical(id="restore-panel"):
            yield Label("Unsaved changes recovered", id="restore-title")
            yield Label(
                f'"{self._name}" has newer unsaved changes from a previous '
                "session (an autosave). Restore them?",
                id="restore-message",
            )
            yield Label(
                f"[{hk}]R[/] restore  ·  [{hk}]D[/] discard  ·  "
                f"[{hk}]Esc[/] decide later",
                id="restore-hint",
            )

    def action_restore(self) -> None:
        self.dismiss("restore")

    def action_discard(self) -> None:
        self.dismiss("discard")

    def action_later(self) -> None:
        self.dismiss("later")

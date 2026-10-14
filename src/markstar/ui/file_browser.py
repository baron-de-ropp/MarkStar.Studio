"""Shared terminal file-explorer modal for Open / Save / Open Folder / Export.

Works-style: a navigable directory list is the main surface; a path field stays
available for typing or Tab-complete. Dismisses with the chosen path string, or
None on cancel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

from markstar.domain.filebrowser import BrowserEntry, list_browser_entries
from markstar.ui.path_input import PathInput
from markstar.ui.themes import token

BrowserMode = Literal["file", "folder", "save"]


def _quiet_icon(entry: BrowserEntry) -> str:
    """Two-character quiet glyph — folders and file kinds, not desktop icons."""
    if entry.is_parent or entry.is_dir:
        return "+ "
    suffix = Path(entry.name).suffix.lower()
    if suffix in {".md", ".markdown", ".mdown", ".mkd", ".mdx", ".mdtext", ".txt"}:
        return "# "
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}:
        return "* "
    if suffix == ".pdf":
        return "p "
    return "- "


class FileBrowserScreen(ModalScreen[str | None]):
    """Browse the filesystem; Enter confirms, Esc cancels."""

    CSS = """
    FileBrowserScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #fb-panel {
        width: 78;
        max-width: 94%;
        height: auto;
        max-height: 88%;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #fb-title { text-style: bold; color: $text; }
    #fb-cwd { color: $text-muted; padding-bottom: 1; }
    #fb-list {
        height: auto;
        max-height: 16;
        background: $boost;
        border: none;
    }
    #fb-list > .option-list--option-highlighted {
        background: $accent 45%;
        color: $text;
    }
    #fb-path { width: 100%; margin-top: 1; }
    #fb-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("f2", "focus_path", show=False, priority=True),
        Binding("ctrl+enter", "use_cwd", show=False, priority=True),
    ]

    def __init__(
        self,
        title: str,
        *,
        mode: BrowserMode = "file",
        start: Path | str | None = None,
        initial: str = "",
        hint: str = "",
    ) -> None:
        super().__init__()
        self._title = title
        self._mode = mode
        self._hint = hint
        start_path = Path(start).expanduser() if start else Path.cwd()
        if initial:
            init = Path(initial).expanduser()
            if init.suffix or self._mode == "save":
                # initial is a file path — browse its parent, keep the name in the field
                if init.parent.is_dir():
                    start_path = init.parent
                self._initial_field = str(init)
            elif init.is_dir():
                start_path = init
                self._initial_field = str(init) + "/"
            else:
                self._initial_field = initial
        else:
            self._initial_field = str(start_path) + ("/" if mode != "file" else "/")
        try:
            self._cwd = start_path.resolve()
        except OSError:
            self._cwd = Path.cwd()
        self._entries: list[BrowserEntry] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="fb-panel"):
            yield Label(self._title, id="fb-title")
            yield Label(str(self._cwd), id="fb-cwd")
            yield OptionList(id="fb-list")
            yield PathInput(value=self._initial_field, id="fb-path")
            yield Label(self._default_hint(), id="fb-hint")

    def _default_hint(self) -> str:
        if self._hint:
            return self._hint
        hk = token(self.app, "hint-key")
        if self._mode == "folder":
            return (
                f"[{hk}]Enter[/] open / enter  ·  [{hk}]F2[/] path  ·  "
                f"[{hk}]Esc[/] cancel"
            )
        if self._mode == "save":
            return (
                f"[{hk}]Enter[/] save / enter folder  ·  [{hk}]F2[/] edit path  ·  "
                f"[{hk}]Esc[/] cancel"
            )
        return (
            f"[{hk}]Enter[/] open / enter folder  ·  [{hk}]F2[/] path  ·  "
            f"[{hk}]Esc[/] cancel"
        )

    def on_mount(self) -> None:
        self._reload_list()
        self.query_one("#fb-list", OptionList).focus()

    def _reload_list(self) -> None:
        self._entries = list_browser_entries(self._cwd, include_parent=True)
        ol = self.query_one("#fb-list", OptionList)
        ol.clear_options()
        options: list[Option] = []
        if self._mode == "folder":
            options.append(
                Option(
                    f"  [Use this folder — {self._cwd.name or self._cwd}]",
                    id="::cwd",
                )
            )
        elif self._mode == "save":
            name = Path(self.query_one("#fb-path", PathInput).value).name or "untitled.md"
            options.append(Option(f"  [Save as {name}]", id="::save"))
        for i, entry in enumerate(self._entries):
            icon = _quiet_icon(entry)
            label = f"{icon}{entry.name}" + (
                "/" if entry.is_dir and not entry.is_parent else ""
            )
            options.append(Option(label, id=str(i)))
        ol.add_options(options)
        if options:
            ol.highlighted = 0
        try:
            self.query_one("#fb-cwd", Label).update(str(self._cwd))
        except Exception:
            pass
        # Keep the path field aligned with the directory we're browsing.
        path_inp = self.query_one("#fb-path", PathInput)
        if self._mode == "save":
            name = Path(path_inp.value).name if path_inp.value.strip() else ""
            path_inp.value = str(self._cwd / name) if name else str(self._cwd) + "/"
        elif self._mode == "folder":
            path_inp.value = str(self._cwd) + "/"
        else:
            path_inp.value = str(self._cwd) + "/"
        path_inp.cursor_position = len(path_inp.value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_focus_path(self) -> None:
        self.query_one("#fb-path", PathInput).focus()

    def action_use_cwd(self) -> None:
        if self._mode == "folder":
            self.dismiss(str(self._cwd))

    def _navigate(self, directory: Path) -> None:
        try:
            self._cwd = directory.expanduser().resolve()
        except OSError:
            return
        self._reload_list()
        self.query_one("#fb-list", OptionList).focus()

    def _selected_entry(self) -> BrowserEntry | None:
        ol = self.query_one("#fb-list", OptionList)
        opt_id = ol.get_option_at_index(ol.highlighted).id if ol.highlighted is not None else None
        if opt_id is None or opt_id == "::cwd":
            return None
        try:
            return self._entries[int(opt_id)]
        except (ValueError, IndexError):
            return None

    def _confirm_from_list(self) -> None:
        ol = self.query_one("#fb-list", OptionList)
        if ol.highlighted is None:
            return
        opt = ol.get_option_at_index(ol.highlighted)
        if opt.id == "::cwd":
            self.dismiss(str(self._cwd))
            return
        if opt.id == "::save":
            raw = self.query_one("#fb-path", PathInput).value.strip()
            if raw:
                self.dismiss(raw)
            return
        entry = self._selected_entry()
        if entry is None:
            return
        if entry.is_dir:
            self._navigate(entry.path)
            return
        # File row — folder mode ignores files; file/save modes pick the path.
        if self._mode == "folder":
            return
        self.dismiss(str(entry.path))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._confirm_from_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        raw = event.value.strip().strip('"').strip("'")
        if not raw:
            return
        path = Path(raw).expanduser()
        # Typing a directory and pressing Enter navigates there in the list.
        if path.is_dir() and self._mode in ("file", "folder", "save"):
            self._navigate(path)
            return
        self.dismiss(raw)
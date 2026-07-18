"""Prose TUI entrypoint (P0 shell + P1 commands / menus / find)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual import events
from textual.widgets import Input, Label, Static, TextArea
from textual.widgets.text_area import Selection

from prose import __version__
from prose.commands.registry import Command, CommandRegistry
from prose.domain.document import Document
from prose.domain.motion import paragraph_down, paragraph_up, word_left, word_right
from prose.domain.search import find_next, find_prev, replace_all, replace_match
from prose.domain.workspace import Workspace
from prose.ui.find_bar import FindBar
from prose.ui.menu_screen import MenuScreen
from prose.ui.themes import DEFAULT_THEME_NAME, VSCODE_DARK

# Keys that mean "next/prev tab" depending on how the terminal encodes Ctrl+Shift+,/.
_NEXT_TAB_KEYS = frozenset(
    {
        "ctrl+shift+.",
        "ctrl+shift+full_stop",
        "ctrl+shift+period",
        "ctrl+shift+greater_than",
        "ctrl+greater_than",
        "ctrl+shift+right_angle_bracket",
    }
)
_PREV_TAB_KEYS = frozenset(
    {
        "ctrl+shift+,",
        "ctrl+shift+comma",
        "ctrl+shift+less_than",
        "ctrl+less_than",
        "ctrl+shift+left_angle_bracket",
    }
)


class ProseTextArea(TextArea):
    """TextArea that never inserts when a tab-switch chord is pressed.

    Some terminals deliver Ctrl+Shift+. as a printable '>' unless we intercept
    before TextArea's insert path.
    """

    async def _on_key(self, event: events.Key) -> None:
        key = event.key
        # Also match bare angle brackets if modifiers are encoded only in key name
        if key in _NEXT_TAB_KEYS or key in {"ctrl+shift+>"}:
            event.stop()
            event.prevent_default()
            self.app.cmd_next_tab()
            return
        if key in _PREV_TAB_KEYS or key in {"ctrl+shift+<"}:
            event.stop()
            event.prevent_default()
            self.app.cmd_prev_tab()
            return
        await super()._on_key(event)


class ProseApp(App[None]):
    """Writing shell with command registry, menus, and find/replace."""

    TITLE = "Prose"
    # Disable Textual's built-in command palette — we use a classic menu ribbon.
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }

    #main {
        height: 1fr;
        background: $background;
    }

    /* Outer prose margin (design default ~5 cols; full config later) */
    #tab-strip {
        height: auto;
        background: $background;
        padding: 0 5;
    }

    #tab-pad-top {
        height: 1;
        background: $background;
    }

    #tab-label {
        height: 1;
        /* Quieter than prose body — active tab slightly brighter via markup */
        color: $text-muted;
        text-style: none;
        background: $background;
        padding: 0 0;
    }

    /* Top rule: full width of tab-strip content (strip already has padding 0 5) */
    #tab-rule {
        height: 1;
        width: 100%;
        color: $text-muted 22%;
        background: $background;
    }

    /* Seamless prose surface — no frame, same color as the rest of the app.
       Left padding only so the scrollbar sits flush on the right edge. */
    #editor {
        height: 1fr;
        border: none;
        margin: 0;
        padding: 0 0 0 5;
        background: $background;
        /* Thin scrollbar (1 cell), muted like tab filename, docked to the right */
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 0;
        scrollbar-gutter: auto;
        scrollbar-background: $background;
        scrollbar-background-hover: $background;
        scrollbar-background-active: $background;
        /* Nearly invisible until hover/drag */
        scrollbar-color: $text-muted 12%;
        scrollbar-color-hover: $text-muted 45%;
        scrollbar-color-active: $text-muted 55%;
        scrollbar-corner-color: $background;
    }

    #editor:focus {
        border: none;
        background: $background;
    }

    #editor > .text-area--cursor-line {
        background: $background;
    }

    /* Bottom chrome: rule · pad · hints+metrics · pad */
    #bottom-chrome {
        height: auto;
        background: $background;
        dock: bottom;
    }

    /* Bottom rule row: 5-col pad + rule fills remaining (aligns with prose) */
    #status-rule-row {
        height: 1;
        width: 100%;
        background: $background;
        padding: 0 1 0 0;
    }

    #status-rule-pad {
        width: 5;
        height: 1;
        background: $background;
    }

    #status-rule {
        width: 1fr;
        height: 1;
        color: $text-muted 22%;
        background: $background;
        text-style: none;
    }

    #support-pad-top, #support-pad-bottom {
        height: 1;
        background: $background;
    }

    #support-row {
        height: 1;
        width: 100%;
        background: $background;
        padding: 0 1 0 5;
    }

    #support-hints {
        width: 1fr;
        height: 1;
        background: $background;
        color: $text-muted;
    }

    #support-metrics {
        width: auto;
        height: 1;
        background: $background;
        color: $text-muted;
        text-align: right;
        padding: 0 1 0 2;
    }
    """

    # Matches design-spec prose measure / margin defaults (Preferences later).
    _PROSE_MARGIN_LEFT = 5
    _PROSE_MAX_WIDTH = 120

    # Menu openers. F9 is the reliable primary (reaches the app in most terminals).
    # Ctrl+Shift+P is often captured by the host terminal/IDE before Prose sees it.
    # Avoid Alt and Ctrl+M (terminals steal Alt; Ctrl+M == Enter).
    BINDINGS = [
        Binding(
            "f9",
            "show_menu",
            "Menu",
            show=True,
            priority=True,
            key_display="F9",
        ),
        Binding(
            "ctrl+shift+p",
            "show_menu",
            "Menu",
            show=False,
            priority=True,
            key_display="Ctrl+Shift+P",
        ),
        # Tab switching (Ctrl+Shift = across open files; ,/. keys ≈ < > direction).
        # With Shift held, terminals often report greater_than/less_than — not full_stop/comma.
        Binding("ctrl+shift+full_stop", "next_tab", "Next tab", show=False, priority=True),
        Binding("ctrl+shift+greater_than", "next_tab", "Next tab", show=False, priority=True),
        Binding("ctrl+shift+period", "next_tab", "Next tab", show=False, priority=True),
        Binding("ctrl+greater_than", "next_tab", "Next tab", show=False, priority=True),
        Binding("ctrl+shift+comma", "prev_tab", "Prev tab", show=False, priority=True),
        Binding("ctrl+shift+less_than", "prev_tab", "Prev tab", show=False, priority=True),
        Binding("ctrl+less_than", "prev_tab", "Prev tab", show=False, priority=True),
        Binding("ctrl+right", "word_right", "Word right", show=False, priority=True),
        Binding("ctrl+left", "word_left", "Word left", show=False, priority=True),
        Binding("ctrl+up", "paragraph_up", "Paragraph up", show=False, priority=True),
        Binding("ctrl+down", "paragraph_down", "Paragraph down", show=False, priority=True),
        Binding("alt+up", "move_line_up", "Move line up", show=False, priority=True),
        Binding("alt+down", "move_line_down", "Move line down", show=False, priority=True),
        Binding("ctrl+shift+d", "duplicate_line", "Duplicate line", show=False, priority=True),
    ]

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self.register_theme(VSCODE_DARK)
        self.theme = DEFAULT_THEME_NAME
        self._path_arg = path
        self.workspace = Workspace()
        self._syncing = False
        self.registry = CommandRegistry()
        self._last_find_end = 0
        self._build_commands()

    @property
    def document(self) -> Document:
        return self.workspace.active

    def _build_commands(self) -> None:
        r = self.registry

        def add(
            id: str,
            label: str,
            menu: str,
            handler,
            binding: str | None = None,
            enabled=None,
        ) -> None:
            r.register(
                Command(
                    id=id,
                    label=label,
                    menu=menu,
                    binding=binding,
                    handler=handler,
                    enabled=enabled,
                )
            )

        add("new_file", "New File", "File", self.cmd_new_file, "ctrl+n")
        add("open_file", "Open File…", "File", self.cmd_open_file, "ctrl+o")
        add("close", "Close", "File", self.cmd_close, "ctrl+w")
        add("close_all", "Close All", "File", self.cmd_close_all, "ctrl+alt+w")
        add("save", "Save", "File", self.cmd_save, "ctrl+s")
        add("save_as", "Save As…", "File", self.cmd_save_as, "ctrl+shift+s")
        add("save_all", "Save All", "File", self.cmd_save_all, "ctrl+alt+s")
        add("quit", "Exit", "File", self.cmd_quit, "ctrl+q")
        add("next_tab", "Next Tab", "View", self.cmd_next_tab, "ctrl+shift+full_stop")
        add("prev_tab", "Previous Tab", "View", self.cmd_prev_tab, "ctrl+shift+comma")

        add(
            "undo",
            "Undo",
            "Edit",
            self.cmd_undo,
            "ctrl+z",
            enabled=lambda: self.document.can_undo,
        )
        add(
            "redo",
            "Redo",
            "Edit",
            self.cmd_redo,
            "ctrl+shift+z",
            enabled=lambda: self.document.can_redo,
        )
        add("find", "Find…", "Edit", self.cmd_find, "ctrl+f")
        add("replace", "Replace…", "Edit", self.cmd_replace, "ctrl+h")
        add("find_next", "Find Next", "Edit", self.cmd_find_next)
        add("find_prev", "Find Previous", "Edit", self.cmd_find_prev)
        add("replace_one", "Replace Selection", "Edit", self.cmd_replace_one)
        add("replace_all", "Replace All", "Edit", self.cmd_replace_all)
        add("go_to_line", "Go To Line…", "Edit", self.cmd_go_to_line, "ctrl+g")
        add("select_all", "Select All", "Edit", self.cmd_select_all, "ctrl+a")

        add("toggle_soft_wrap", "Soft Wrap", "View", self.cmd_toggle_soft_wrap, "alt+z")

        add("about", "About…", "Help", self.cmd_about)
        add(
            "keyboard_shortcuts",
            "Keyboard Shortcuts…",
            "Help",
            self.cmd_keyboard_shortcuts,
        )
        add("send_feedback", "Send Feedback…", "Help", self.cmd_send_feedback)

    def compose(self) -> ComposeResult:
        with Vertical(id="main"):
            # blank · filename · blank · thin rule · (find) · editor
            with Vertical(id="tab-strip"):
                yield Static("", id="tab-pad-top")
                yield Static("   Untitled   |", id="tab-label")  # 3 lead; 3 trail slots; middle → •
                # No blank row under the tab label — rule sits tight underneath
                yield Static("", id="tab-rule")
            yield FindBar(id="find-bar")
            yield ProseTextArea(id="editor")
            with Vertical(id="bottom-chrome"):
                with Horizontal(id="status-rule-row"):
                    yield Static("", id="status-rule-pad")
                    yield Static("", id="status-rule")
                yield Static("", id="support-pad-top")
                with Horizontal(id="support-row"):
                    yield Static("", id="support-hints")
                    yield Static("", id="support-metrics")
                yield Static("", id="support-pad-bottom")

    # Support-strip shortcuts (key label shown in blue, description dim).
    _SUPPORT_HINTS: list[tuple[str, str]] = [
        ("F9", "Menu"),
        ("Ctrl+Shift+.", "Next tab"),  # full_stop key; , is previous
        ("Ctrl+S", "Save"),
        ("Ctrl+F", "Find"),
        ("Ctrl+Z", "Undo"),
        ("Ctrl+Q", "Quit"),
    ]

    def on_mount(self) -> None:
        for key, command_id, label in self.registry.bindings():
            # App.bind() has no priority= kwarg; BindingMap.bind does.
            self._bindings.bind(
                key,
                f"run_command('{command_id}')",
                description=label,
                show=False,
                priority=True,
            )
        self.refresh_bindings()
        self._refresh_support_hints()

        editor = self.query_one("#editor", ProseTextArea)
        editor.soft_wrap = True
        editor.show_line_numbers = False
        # No distinct "paper" band or gutter chrome
        editor.highlight_cursor_line = False
        # Editor syntax/selection colors: Textual's built-in VS Code Dark map
        try:
            from textual.widgets.text_area import TextAreaTheme

            vs = TextAreaTheme.get_builtin_theme("vscode_dark")
            if vs is not None:
                editor.register_theme(vs)
                editor.theme = "vscode_dark"
        except Exception:
            pass

        if self._path_arg is not None:
            if self._path_arg.exists():
                self.workspace.open_path(self._path_arg)
            else:
                self.workspace.active.path = self._path_arg
        self._load_active_into_editor()
        editor.focus()
        self._refresh_status()
        self.call_after_refresh(self._update_prose_rules)

    def on_resize(self, event) -> None:
        self.call_after_refresh(self._update_prose_rules)

    def _update_prose_rules(self) -> None:
        """Fill top/bottom rules with ─ to match laid-out width (prose column)."""
        for rule_id in ("#status-rule", "#tab-rule"):
            try:
                rule = self.query_one(rule_id, Static)
            except Exception:
                continue
            # Use the widget's actual laid-out width so we track the prose surface
            width = max(1, rule.size.width)
            if width <= 1:
                # Layout not ready — try again next frame
                self.call_after_refresh(self._update_prose_rules)
                return
            rule.update("─" * width)

    @on(TextArea.Changed)
    def _on_editor_changed(self, event: TextArea.Changed) -> None:
        if self._syncing:
            return
        new_text = event.text_area.text
        if new_text == self.document.text:
            return
        self.document.set_text(new_text)
        self._refresh_status()

    @on(TextArea.SelectionChanged)
    def _on_selection_changed(self, event: TextArea.SelectionChanged) -> None:
        self._refresh_metrics()

    def _sync_document_from_editor(self) -> None:
        editor = self.query_one("#editor", TextArea)
        if editor.text != self.document.text:
            self.document.set_text(editor.text)

    def _push_document_to_editor(self) -> None:
        self._load_active_into_editor()
        self._refresh_metrics()

    def _load_active_into_editor(self) -> None:
        editor = self.query_one("#editor", TextArea)
        self._syncing = True
        editor.load_text(self.document.text)
        self._syncing = False

    def _switch_tab(self, switcher) -> None:
        """Sync editor → doc, switch tab via callable, load new doc."""
        self._sync_document_from_editor()
        switcher()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()

    def _cursor_index(self) -> int:
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        try:
            return int(editor.document.get_index_from_location((row, col)))
        except Exception:
            lines = editor.text.split("\n")
            idx = sum(len(lines[i]) + 1 for i in range(min(row, len(lines))))
            return idx + col

    def _select_range(self, start: int, end: int) -> None:
        editor = self.query_one("#editor", TextArea)
        try:
            start_loc = editor.document.get_location_from_index(start)
            end_loc = editor.document.get_location_from_index(end)
            editor.selection = Selection(start_loc, end_loc)
            editor.scroll_cursor_visible()
        except Exception:
            pass

    def _refresh_support_hints(self) -> None:
        """Blue keys + dim labels (labels/pipes inherit $text-muted from CSS)."""
        parts: list[str] = []
        for key, desc in self._SUPPORT_HINTS:
            # Only the key is colored; description + spaces use widget $text-muted
            # (same as tab filename). Explicit hex on labels was fighting theme/CSS.
            parts.append(f"[#007ACC]{key}[/] {desc}")
        try:
            self.query_one("#support-hints", Static).update("  |  ".join(parts))
        except Exception:
            pass

    def _cursor_line_col(self) -> tuple[int, int]:
        """1-based line and column of the caret."""
        try:
            editor = self.query_one("#editor", TextArea)
            row, col = editor.cursor_location
            return row + 1, col + 1
        except Exception:
            return 1, 1

    def _refresh_metrics(self) -> None:
        """Right-aligned: Ln:Col (volatile first), words, Markdown flavor."""
        line, col = self._cursor_line_col()
        words = self.document.word_count()
        # Fixed-ish order: line/col changes often — keep it leftmost of the group
        # so word count and flavor don't jump as the caret moves.
        text = f"Ln {line}, Col {col}  │  {words} words  │  CommonMark"
        try:
            self.query_one("#support-metrics", Static).update(text)
        except Exception:
            pass

    def _format_tab_chip(self, doc: Document, *, active: bool) -> str:
        name = doc.path.name if doc.path else "Untitled"
        # Three slots after the name: " _ _ _|" — middle slot is dirty • (stable width)
        mid = "•" if doc.dirty else " "
        chip = f"   {name} {mid} |"
        # Match footer hint labels ($text-muted / dull grey) — not body-text bright
        if active:
            return f"[#858585]{chip}[/]"
        return f"[#858585 65%]{chip}[/]"

    def _refresh_status(self) -> None:
        """Tab strip (all open docs), support metrics, and terminal title."""
        chips = [
            self._format_tab_chip(doc, active=(i == self.workspace.active_index))
            for i, doc in enumerate(self.workspace.documents)
        ]
        try:
            self.query_one("#tab-label", Static).update("".join(chips))
        except Exception:
            pass

        self._refresh_metrics()
        self.call_after_refresh(self._update_prose_rules)
        name = self.document.path.name if self.document.path else "Untitled"
        self.title = f"{name}{' •' if self.document.dirty else ''}"

    def action_run_command(self, command_id: str) -> None:
        self.registry.execute(command_id)

    def action_show_menu(self) -> None:
        self._open_menu(None)

    def on_key(self, event: Key) -> None:
        """Hard fallback: some terminals drop priority bindings while TextArea is focused."""
        if isinstance(self.screen, MenuScreen):
            return
        if event.key == "f9" or event.key == "ctrl+shift+p":
            event.stop()
            self._open_menu(None)
            return
        # Tab switching — include greater/less-than (what Shift+,/. often becomes)
        if event.key in {
            "ctrl+shift+.",
            "ctrl+shift+full_stop",
            "ctrl+shift+period",
            "ctrl+shift+greater_than",
            "ctrl+greater_than",
            "ctrl+shift+right_angle_bracket",
        }:
            event.stop()
            self.cmd_next_tab()
            return
        if event.key in {
            "ctrl+shift+,",
            "ctrl+shift+comma",
            "ctrl+shift+less_than",
            "ctrl+less_than",
            "ctrl+shift+left_angle_bracket",
        }:
            event.stop()
            self.cmd_prev_tab()
            return

    def _open_menu(self, menu_name: str | None) -> None:
        # Avoid stacking duplicate ribbons
        if isinstance(self.screen, MenuScreen):
            return

        def on_close(command_id: str | None) -> None:
            if command_id:
                try:
                    self.registry.execute(command_id)
                except Exception as exc:
                    self.notify(f"Command failed: {exc}", severity="error")
            try:
                self.query_one("#editor", TextArea).focus()
            except Exception:
                pass

        try:
            self.push_screen(MenuScreen(self.registry, menu_name), on_close)
        except Exception as exc:
            self.notify(f"Could not open menu: {exc}", severity="error")

    def cmd_new_file(self) -> None:
        self._sync_document_from_editor()
        self.workspace.new_document()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        self.notify("New file")

    def cmd_open_file(self) -> None:
        self.notify(
            "Open: prose path/to/file.md  (file dialog later)",
            severity="information",
        )

    def cmd_close(self) -> None:
        self._sync_document_from_editor()
        was_dirty = self.document.dirty
        self.workspace.close_active()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        if was_dirty:
            self.notify("Closed tab (unsaved buffer discarded)", severity="warning")

    def cmd_close_all(self) -> None:
        self._sync_document_from_editor()
        self.workspace.close_all()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()

    def cmd_save_all(self) -> None:
        self._sync_document_from_editor()
        saved = 0
        skipped = 0
        for doc in self.workspace.documents:
            if doc.path is None:
                skipped += 1
                continue
            try:
                doc.save()
                saved += 1
            except OSError:
                skipped += 1
        self._refresh_status()
        self.notify(f"Saved {saved} file(s)" + (f", {skipped} skipped" if skipped else ""))

    def cmd_next_tab(self) -> None:
        self._switch_tab(self.workspace.next_tab)

    def cmd_prev_tab(self) -> None:
        self._switch_tab(self.workspace.prev_tab)

    def action_next_tab(self) -> None:
        self.cmd_next_tab()

    def action_prev_tab(self) -> None:
        self.cmd_prev_tab()

    def cmd_save(self) -> None:
        self._sync_document_from_editor()
        if self.document.path is None:
            self._prompt_and_save(title="Save As — where should this file go?")
            return
        self._write_active_document()

    def cmd_save_as(self) -> None:
        self._sync_document_from_editor()
        initial = ""
        if self.document.path is not None:
            initial = str(self.document.path)
        self._prompt_and_save(title="Save As — enter a path", initial=initial)

    def _write_active_document(self, path: Path | None = None) -> None:
        try:
            self.document.save(path)
            self.notify(f"Saved {self.document.path}")
            self._refresh_status()
        except OSError as exc:
            self.notify(f"Save failed: {exc}", severity="error")
        except ValueError as exc:
            self.notify(str(exc), severity="warning")

    def _prompt_and_save(self, *, title: str, initial: str = "") -> None:
        """Ask for a filesystem path, then save the active buffer there."""

        async def _run() -> None:
            raw = await self.push_screen_wait(
                _PathPrompt(
                    title,
                    initial=initial or str(Path.cwd() / "untitled.md"),
                    hint="Enter path and press Enter · Esc cancel · ~ allowed",
                )
            )
            if raw is None:
                return
            path = self._normalize_save_path(raw)
            if path is None:
                self.notify("Empty path — not saved", severity="warning")
                return
            # If another tab already has this path, refuse to clobber via Save As
            if path.exists() and (
                self.document.path is None
                or path.resolve() != self.document.path.resolve()
            ):
                # Still allow overwrite; warn
                self.notify(f"Overwriting {path.name}", severity="warning")
            self._write_active_document(path)

        self.run_worker(_run())

    @staticmethod
    def _normalize_save_path(raw: str) -> Path | None:
        text = raw.strip().strip('"').strip("'")
        if not text:
            return None
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        # Default extension for bare names
        if path.suffix == "":
            path = path.with_suffix(".md")
        return path

    def action_quit(self) -> None:
        """Override Textual's default action_quit (Ctrl+Q) so we can confirm dirty tabs.

        Textual binds ctrl+q → ``quit`` → ``App.action_quit`` which exits immediately.
        That bypassed ``cmd_quit`` / the command registry.
        """
        self.cmd_quit()

    def _unsaved_documents(self) -> list[Document]:
        """Dirty workspace buffers, after syncing the focused editor into the active doc."""
        self._sync_document_from_editor()
        return self.workspace.dirty_documents()

    def cmd_quit(self) -> None:
        dirty = self._unsaved_documents()
        if not dirty:
            self.exit()
            return

        names: list[str] = []
        for doc in dirty:
            names.append(doc.path.name if doc.path else "Untitled")
        if len(names) == 1:
            detail = f'"{names[0]}" has unsaved changes.'
        else:
            listed = ", ".join(names[:4])
            if len(names) > 4:
                listed += "…"
            detail = f"{len(names)} tabs have unsaved changes ({listed})."

        async def _confirm() -> None:
            ok = await self.push_screen_wait(
                _ConfirmQuit(
                    title="Quit Prose?",
                    message=detail + "\nQuit anyway and discard unsaved work?",
                )
            )
            if ok:
                self.exit()

        self.run_worker(_confirm())

    def cmd_undo(self) -> None:
        self._sync_document_from_editor()
        if self.document.undo():
            self._push_document_to_editor()
            self._refresh_status()

    def cmd_redo(self) -> None:
        self._sync_document_from_editor()
        if self.document.redo():
            self._push_document_to_editor()
            self._refresh_status()

    def cmd_find(self) -> None:
        self.query_one("#find-bar", FindBar).show(replace=False)

    def cmd_replace(self) -> None:
        self.query_one("#find-bar", FindBar).show(replace=True)

    def cmd_find_next(self) -> None:
        self._find_direction("next")

    def cmd_find_prev(self) -> None:
        self._find_direction("prev")

    def cmd_replace_one(self) -> None:
        self._sync_document_from_editor()
        bar = self.query_one("#find-bar", FindBar)
        query = bar.query
        if not query:
            self.notify("Open Replace (Ctrl+H) and enter a find string", severity="warning")
            self.cmd_replace()
            return
        cursor = self._cursor_index()
        match = find_next(self.document.text, query, start=cursor)
        if match is None:
            match = find_next(self.document.text, query, start=0)
        if match is None:
            self.notify(f"Not found: {query!r}", severity="warning")
            return
        new_m = replace_match(self.document, match, bar.replacement)
        self._push_document_to_editor()
        self._select_range(new_m.start, new_m.end)
        self._last_find_end = new_m.end
        self._refresh_status()

    def cmd_replace_all(self) -> None:
        self._sync_document_from_editor()
        bar = self.query_one("#find-bar", FindBar)
        query = bar.query
        if not query:
            self.notify("Open Replace (Ctrl+H) and enter a find string", severity="warning")
            self.cmd_replace()
            return
        n = replace_all(self.document, query, bar.replacement)
        self._push_document_to_editor()
        self._refresh_status()
        self.notify(f"Replaced {n} occurrence(s)")

    def cmd_go_to_line(self) -> None:
        self._sync_document_from_editor()
        editor = self.query_one("#editor", TextArea)
        lines = max(self.document.text.count("\n") + 1, 1)

        async def _prompt() -> None:
            raw = await self.push_screen_wait(_LinePrompt(f"Go to line (1–{lines}):"))
            if raw is None:
                return
            try:
                n = int(raw.strip())
            except ValueError:
                self.notify("Not a number", severity="warning")
                return
            n = max(1, min(n, lines))
            editor.move_cursor((n - 1, 0))
            editor.scroll_cursor_visible()
            editor.focus()

        self.run_worker(_prompt())

    def cmd_select_all(self) -> None:
        self.query_one("#editor", TextArea).select_all()

    def _move_caret_to_index(self, index: int) -> None:
        editor = self.query_one("#editor", TextArea)
        try:
            loc = editor.document.get_location_from_index(index)
            editor.move_cursor(loc)
            editor.scroll_cursor_visible()
        except Exception:
            pass
        self._refresh_metrics()

    def action_word_left(self) -> None:
        self._sync_document_from_editor()
        idx = word_left(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_word_right(self) -> None:
        self._sync_document_from_editor()
        idx = word_right(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_paragraph_up(self) -> None:
        self._sync_document_from_editor()
        idx = paragraph_up(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_paragraph_down(self) -> None:
        self._sync_document_from_editor()
        idx = paragraph_down(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_move_line_up(self) -> None:
        self._sync_document_from_editor()
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        if row <= 0:
            return
        lines = self.document.text.split("\n")
        lines[row - 1], lines[row] = lines[row], lines[row - 1]
        self.document.set_text("\n".join(lines))
        self._load_active_into_editor()
        editor.move_cursor((row - 1, min(col, len(lines[row - 1]))))
        self._refresh_status()

    def action_move_line_down(self) -> None:
        self._sync_document_from_editor()
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        lines = self.document.text.split("\n")
        if row >= len(lines) - 1:
            return
        lines[row], lines[row + 1] = lines[row + 1], lines[row]
        self.document.set_text("\n".join(lines))
        self._load_active_into_editor()
        editor.move_cursor((row + 1, min(col, len(lines[row + 1]))))
        self._refresh_status()

    def action_duplicate_line(self) -> None:
        self._sync_document_from_editor()
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        lines = self.document.text.split("\n")
        lines.insert(row + 1, lines[row])
        self.document.set_text("\n".join(lines))
        self._load_active_into_editor()
        editor.move_cursor((row + 1, col))
        self._refresh_status()

    def cmd_toggle_soft_wrap(self) -> None:
        editor = self.query_one("#editor", TextArea)
        editor.soft_wrap = not editor.soft_wrap
        self.notify(f"Soft wrap {'on' if editor.soft_wrap else 'off'}")

    def cmd_about(self) -> None:
        self.notify(f"Prose {__version__} — terminal Markdown word processor · MIT")

    def cmd_keyboard_shortcuts(self) -> None:
        lines = [f"{cmd.binding:18} {cmd.label}" for cmd in self.registry if cmd.binding]
        self.notify("\n".join(lines) if lines else "(no bindings)", timeout=8)

    def cmd_send_feedback(self) -> None:
        self.notify(
            "Feedback: daudzegir@gmail.com — I likely won't listen (but try anyway)",
            timeout=6,
        )

    @on(FindBar.Submitted)
    def _on_find_submitted(self, event: FindBar.Submitted) -> None:
        self._find_direction(event.direction)

    @on(FindBar.Dismissed)
    def _on_find_dismissed(self) -> None:
        self.query_one("#editor", TextArea).focus()

    def _find_direction(self, direction: str) -> None:
        self._sync_document_from_editor()
        bar = self.query_one("#find-bar", FindBar)
        query = bar.query
        if not query:
            self.notify("Enter a find string", severity="warning")
            bar.show(replace=False)
            return

        text = self.document.text
        cursor = self._cursor_index()

        if direction == "next":
            start = cursor
            # If already on a match, advance past it
            if start < self._last_find_end:
                start = self._last_find_end
            match = find_next(text, query, start=start)
        else:
            match = find_prev(text, query, start=cursor)

        if match is None:
            self.notify(f"Not found: {query!r}", severity="warning")
            return

        self._last_find_end = match.end
        self._select_range(match.start, match.end)


class _LinePrompt(ModalScreen[str | None]):
    """Tiny modal to ask for a line number."""

    CSS = """
    _LinePrompt {
        align: center middle;
    }
    #line-panel {
        width: 40;
        height: auto;
        background: $surface;
        border: tall $accent 50%;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("enter", "submit", show=False),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="line-panel"):
            yield Label(self.prompt)
            yield Input(id="line-input")

    def on_mount(self) -> None:
        self.query_one("#line-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#line-input", Input).value)


class _PathPrompt(ModalScreen[str | None]):
    """Modal path entry for Save / Save As (OpenCode-soft panel)."""

    CSS = """
    _PathPrompt {
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
            yield Input(value=self._initial, placeholder="/path/to/file.md", id="path-input")
            yield Label(self._hint or "Enter · save   Esc · cancel", id="path-hint")

    def on_mount(self) -> None:
        inp = self.query_one("#path-input", Input)
        inp.focus()
        # Select basename so typing replaces the default name quickly
        if self._initial:
            try:
                text = self._initial
                slash = max(text.rfind("/"), text.rfind("\\"))
                start = slash + 1 if slash >= 0 else 0
                inp.cursor_position = len(text)
                # Textual Input selection API varies; best-effort
                if hasattr(inp, "action_select_all"):
                    # Prefer selecting only the filename portion when possible
                    pass
            except Exception:
                pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#path-input", Input).value)


class _ConfirmQuit(ModalScreen[bool]):
    """Confirm quitting with dirty buffers. True = quit, False = stay."""

    CSS = """
    _ConfirmQuit {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #quit-panel {
        width: 64;
        max-width: 90%;
        height: auto;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #quit-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }
    #quit-message {
        color: $text-muted;
        padding-bottom: 1;
    }
    #quit-hint {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("n", "cancel", show=False, priority=True),
        Binding("enter", "confirm", show=False, priority=True),
        Binding("y", "confirm", show=False, priority=True),
        Binding("q", "confirm", show=False, priority=True),
    ]

    def __init__(self, *, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-panel"):
            yield Label(self._title, id="quit-title")
            yield Label(self._message, id="quit-message")
            yield Label(
                "[#007ACC]Y[/]/Enter quit  ·  [#007ACC]N[/]/Esc stay",
                id="quit-hint",
            )

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="prose", description="Prose — terminal Markdown word processor"
    )
    parser.add_argument("path", nargs="?", type=Path, help="Markdown file to open")
    parser.add_argument("--version", action="version", version=f"Prose {__version__}")
    args = parser.parse_args(argv)

    app = ProseApp(path=args.path)
    app.run()


if __name__ == "__main__":
    main(sys.argv[1:])

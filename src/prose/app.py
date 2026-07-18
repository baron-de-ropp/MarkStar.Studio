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
from textual.widgets import Input, Label, Static, TextArea
from textual.widgets.text_area import Selection

from prose import __version__
from prose.commands.registry import Command, CommandRegistry
from prose.domain.document import Document
from prose.domain.search import find_next, find_prev, replace_all, replace_match
from prose.ui.find_bar import FindBar
from prose.ui.menu_screen import MenuScreen
from prose.ui.themes import DEFAULT_THEME_NAME, VSCODE_DARK


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
        /* Quieter than prose body — tab chrome, not content */
        color: $text-muted;
        text-style: none;
        background: $background;
        padding: 0 0;
    }

    /* Top rule: full width of tab-strip content (strip already has padding 0 5) */
    #tab-rule {
        height: 1;
        width: 100%;
        color: $text-muted 50%;
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
        color: $text-muted 50%;
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
        # Optional; may not reach the app depending on terminal
        Binding(
            "ctrl+shift+p",
            "show_menu",
            "Menu",
            show=False,
            priority=True,
            key_display="Ctrl+Shift+P",
        ),
    ]

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self.register_theme(VSCODE_DARK)
        self.theme = DEFAULT_THEME_NAME
        self._path_arg = path
        self.document = Document()
        self._syncing = False
        self.registry = CommandRegistry()
        self._last_find_end = 0
        self._build_commands()

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
        add("save", "Save", "File", self.cmd_save, "ctrl+s")
        add("save_as", "Save As…", "File", self.cmd_save_as, "ctrl+shift+s")
        add("quit", "Exit", "File", self.cmd_quit, "ctrl+q")

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
                yield Static("  Untitled  │", id="tab-label")  # mark slot → • when dirty; │ joins rule via ┴
                # No blank row under the tab label — rule sits tight underneath
                yield Static("", id="tab-rule")
            yield FindBar(id="find-bar")
            yield TextArea(id="editor")
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

        editor = self.query_one("#editor", TextArea)
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

        if self._path_arg is not None and self._path_arg.exists():
            self.document = Document.load(self._path_arg)
            self._syncing = True
            editor.load_text(self.document.text)
            self._syncing = False
        elif self._path_arg is not None:
            self.document.path = self._path_arg
        editor.focus()
        self._refresh_status()
        self.call_after_refresh(self._update_prose_rules)

    def on_resize(self, event) -> None:
        self.call_after_refresh(self._update_prose_rules)

    def _tab_cap_column(self) -> int | None:
        """Column index of the tab's │ within the tab-strip content (0-based)."""
        try:
            label = str(self.query_one("#tab-label", Static).render())
        except Exception:
            return None
        # Format is always: "  {name}{mark} │" — cap is the last character
        if not label.endswith("│"):
            idx = label.rfind("│")
            return idx if idx >= 0 else None
        return len(label) - 1

    def _update_prose_rules(self) -> None:
        """Fill top/bottom rules with ─; top rule joins tab cap with ┴."""
        join_col = self._tab_cap_column()
        for rule_id in ("#status-rule", "#tab-rule"):
            try:
                rule = self.query_one(rule_id, Static)
            except Exception:
                continue
            width = max(1, rule.size.width)
            if width <= 1:
                self.call_after_refresh(self._update_prose_rules)
                return
            chars = ["─"] * width
            # Upside-down T under the tab's vertical bar (top rule only)
            if rule_id == "#tab-rule" and join_col is not None and 0 <= join_col < width:
                chars[join_col] = "┴"
            rule.update("".join(chars))

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
        editor = self.query_one("#editor", TextArea)
        self._syncing = True
        editor.load_text(self.document.text)
        self._syncing = False
        self._refresh_metrics()

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

    def _refresh_status(self) -> None:
        """Tab label, support metrics, and terminal title."""
        name = self.document.path.name if self.document.path else "Untitled"
        # Slot right after the filename: space when clean, • when dirty — same width
        mark = "•" if self.document.dirty else " "
        # Box-drawing vertical; joins the rule below via ┴
        tab_text = f"  {name}{mark} │"

        try:
            self.query_one("#tab-label", Static).update(tab_text)
        except Exception:
            pass

        self._refresh_metrics()
        # Re-seat the ┴ under the cap when name/dirty length is unchanged it's free;
        # still cheap to refresh after tab text updates.
        self.call_after_refresh(self._update_prose_rules)
        # Terminal title can show dirty without worrying about tab geometry
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
        self.document = Document()
        self._last_find_end = 0
        self._push_document_to_editor()
        self._refresh_status()
        self.notify("New file")

    def cmd_open_file(self) -> None:
        self.notify(
            "Open: prose path/to/file.md  (file dialog later)",
            severity="information",
        )

    def cmd_save(self) -> None:
        self._sync_document_from_editor()
        if self.document.path is None:
            self.notify("No path — open with: prose path/to/file.md", severity="warning")
            return
        try:
            self.document.save()
            self.notify(f"Saved {self.document.path}")
            self._refresh_status()
        except OSError as exc:
            self.notify(f"Save failed: {exc}", severity="error")

    def cmd_save_as(self) -> None:
        self.notify("Save As: CLI path for now; dialog later", severity="information")

    def cmd_quit(self) -> None:
        self.exit()

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

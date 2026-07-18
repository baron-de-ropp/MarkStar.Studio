"""Prose TUI entrypoint (P0 shell + P1 commands / menus / find)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.style import Style
from rich.text import Text
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
from prose.domain.search import (
    Match,
    find_all,
    find_next,
    replace_all,
    replace_match,
    step_find,
)
from prose.domain.workspace import Workspace
from prose.ui.find_bar import FindBar
from prose.ui.keys import is_replace_all_key, normalize_key
from prose.ui.menu_bar import MenuBar
from prose.ui.themes import DEFAULT_THEME_NAME, VSCODE_DARK

# Soft highlight for non-focused find hits (VS Code–ish findMatchBackground).
# Focused hit stays bright via TextArea selection_style (#264f78).
_SEARCH_MATCH_STYLE = Style(bgcolor="#515C6A")

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

    Also narrows the soft-wrap width so text keeps a 5-column right margin while
    the widget itself (and its scrollbar) runs flush to the window edge. Right
    padding can't do this: Textual carves the scrollbar out of the region left
    over AFTER padding, so padding-right insets the scrollbar as well.

    Search highlights: all matches get a soft background via ``get_line``;
    the focused match is the normal selection (brighter), painted on top.
    """

    # Base wrap_width already reserves the scrollbar column (via
    # scrollable_content_region) and 1 cursor cell; 3 more blank columns makes
    # the full 5-col right inset, so text ends at the same column as the rules
    # (which use `padding: 0 5`).
    EXTRA_RIGHT_MARGIN = 3

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # line_index -> list of (start_col, end_col) character offsets on that line
        self._search_by_line: dict[int, list[tuple[int, int]]] = {}

    @property
    def wrap_width(self) -> int:
        width = super().wrap_width
        return max(0, width - self.EXTRA_RIGHT_MARGIN) if width else width

    def set_search_highlights(self, matches: list[Match]) -> None:
        """Soft-highlight every match. Pass ``[]`` to clear."""
        by_line: dict[int, list[tuple[int, int]]] = {}
        for match in matches:
            try:
                start_loc = self.document.get_location_from_index(match.start)
                end_loc = self.document.get_location_from_index(match.end)
            except Exception:
                continue
            start_row, start_col = start_loc
            end_row, end_col = end_loc
            if start_row == end_row:
                by_line.setdefault(start_row, []).append((start_col, end_col))
                continue
            # Multi-line query: paint each spanned line segment.
            try:
                first_line = self.document.get_line(start_row)
                by_line.setdefault(start_row, []).append((start_col, len(first_line)))
                for row in range(start_row + 1, end_row):
                    line = self.document.get_line(row)
                    by_line.setdefault(row, []).append((0, len(line)))
                by_line.setdefault(end_row, []).append((0, end_col))
            except Exception:
                pass

        if by_line == self._search_by_line:
            return
        self._search_by_line = by_line
        # Strip cache does not include search state — force repaint.
        self._line_cache.clear()
        self.refresh()

    def clear_search_highlights(self) -> None:
        if not self._search_by_line:
            return
        self._search_by_line = {}
        self._line_cache.clear()
        self.refresh()

    def get_line(self, line_index: int) -> Text:
        line = super().get_line(line_index)
        spans = self._search_by_line.get(line_index)
        if spans:
            for start_col, end_col in spans:
                if start_col < end_col:
                    line.stylize(_SEARCH_MATCH_STYLE, start_col, end_col)
        return line

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

    /* Top-line menu ribbon (first terminal row when open). */
    #app-menu {
        dock: top;
        width: 100%;
        height: auto;
    }

    #main {
        height: 1fr;
        background: $background;
    }

    /* Content column: 5 left + text + 1 scrollbar at window edge.
       Right "margin" for rules/metrics is 1 col (scrollbar), not a second pad
       that would push the scrollbar inward. */
    #tab-strip {
        height: auto;
        background: $background;
        /* 5-col inset both sides (right margin clear of scrollbar column) */
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

    /* Editor row: 5-col left gutter + TextArea to the window edge (scrollbar flush).
       The TextArea must have NO right padding: Textual splits the scrollbar off the
       region AFTER shrinking by padding (_compositor.py: region.shrink(styles.gutter)
       then _arrange_scrollbars), so any right pad insets the scrollbar too. The 5-col
       right text inset comes from ProseTextArea.wrap_width instead. scrollbar-gutter:
       stable reserves the bar column even when the document fits, keeping the wrap
       column identical whether or not the bar is drawn. */
    #editor-row {
        height: 1fr;
        width: 100%;
        background: $background;
    }

    #editor-left-pad {
        width: 5;
        height: 1fr;
        background: $background;
    }

    #editor {
        width: 1fr;
        height: 1fr;
        border: none;
        margin: 0;
        /* No padding at all — left inset is the gutter widget, right inset lives in
           ProseTextArea.wrap_width so the scrollbar stays flush at the window edge. */
        padding: 0;
        background: $background;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 0;
        scrollbar-gutter: stable;
        scrollbar-background: $background;
        scrollbar-background-hover: $background;
        scrollbar-background-active: $background;
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

    /* Match tab-strip: 5-col inset both sides */
    #status-rule-row {
        height: 1;
        width: 100%;
        background: $background;
        padding: 0 5;
    }

    #status-rule {
        width: 100%;
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
        /* Same 5-col side inset as rules; scrollbar stays on editor edge only */
        padding: 0 5;
    }

    #support-hints {
        width: 1fr;
        height: 1;
        background: $background;
        color: $text-muted;
        padding: 0;
    }

    #support-metrics {
        width: auto;
        height: 1;
        background: $background;
        color: $text-muted;
        text-align: right;
        padding: 0;
    }
    """

    # Matches design-spec prose measure / margin defaults (Preferences later).
    _PROSE_MARGIN_LEFT = 5
    _PROSE_MAX_WIDTH = 120

    # Menu: Esc is primary (Word/MC-style). F9 remains as alternate.
    # Esc also dismisses find/modals when those are open (see action_esc_key).
    BINDINGS = [
        Binding(
            "escape",
            "esc_key",
            "Menu",
            show=True,
            priority=True,
            key_display="Esc",
        ),
        Binding(
            "f9",
            "show_menu",
            "Menu",
            show=False,
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
        # Find / replace (bindings chosen with the user; bulk = Ctrl+Alt).
        Binding("ctrl+r", "show_replace", "Replace", show=False, priority=True),
        # ctrl+h: only when distinct from Backspace (Kitty keyboard protocol).
        Binding("ctrl+h", "show_replace", "Replace", show=False, priority=True),
        Binding("ctrl+enter", "find_prev", "Find previous", show=False, priority=True),
        Binding("ctrl+alt+r", "replace_all_key", "Replace all", show=False, priority=True),
        Binding("alt+ctrl+r", "replace_all_key", "Replace all", show=False, priority=True),
        Binding("ctrl+alt+R", "replace_all_key", "Replace all", show=False, priority=True),
        Binding("alt+ctrl+R", "replace_all_key", "Replace all", show=False, priority=True),
        # Bulk file ops — bind both modifier orders + letter cases.
        Binding("ctrl+alt+s", "save_all", "Save all", show=False, priority=True),
        Binding("alt+ctrl+s", "save_all", "Save all", show=False, priority=True),
        Binding("ctrl+alt+S", "save_all", "Save all", show=False, priority=True),
        Binding("alt+ctrl+S", "save_all", "Save all", show=False, priority=True),
        Binding("ctrl+shift+s", "save_as", "Save as", show=False, priority=True),
        Binding("ctrl+shift+S", "save_as", "Save as", show=False, priority=True),
        Binding("ctrl+o", "open_file", "Open", show=False, priority=True),
        Binding("ctrl+O", "open_file", "Open", show=False, priority=True),
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
        add("close_others", "Close Others", "File", self.cmd_close_others)  # menu only
        add("close_all", "Close All", "File", self.cmd_close_all)  # menu only
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
        add("replace", "Replace…", "Edit", self.cmd_replace, "ctrl+r")
        add("find_next", "Find Next", "Edit", self.cmd_find_next)  # Enter in find bar
        add("find_prev", "Find Previous", "Edit", self.cmd_find_prev, "ctrl+enter")
        add("replace_one", "Replace", "Edit", self.cmd_replace_one)  # Enter in replace field
        add("replace_all", "Replace All", "Edit", self.cmd_replace_all, "ctrl+alt+r")
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
        # First terminal line when open (dock top) — not a modal overlay.
        yield MenuBar(self.registry, id="app-menu")
        with Vertical(id="main"):
            # blank · filename · blank · thin rule · (find) · editor
            with Vertical(id="tab-strip"):
                yield Static("", id="tab-pad-top")
                yield Static("   Untitled   |", id="tab-label")  # 3 lead; 3 trail slots; middle → •
                # No blank row under the tab label — rule sits tight underneath
                yield Static("", id="tab-rule")
            yield FindBar(id="find-bar")
            with Horizontal(id="editor-row"):
                yield Static("", id="editor-left-pad")
                yield ProseTextArea(id="editor")
            with Vertical(id="bottom-chrome"):
                with Horizontal(id="status-rule-row"):
                    yield Static("", id="status-rule")
                yield Static("", id="support-pad-top")
                with Horizontal(id="support-row"):
                    yield Static("", id="support-hints")
                    yield Static("", id="support-metrics")
                yield Static("", id="support-pad-bottom")

    # Support-strip shortcuts (key label shown in blue, description dim).
    _SUPPORT_HINTS: list[tuple[str, str]] = [
        ("Esc", "Menu"),
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
        # Keep soft find highlights in sync while typing in the buffer.
        try:
            if self.query_one("#find-bar", FindBar).is_visible:
                self._refresh_search_highlights()
        except Exception:
            pass

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
        self._toggle_menu(None)

    def action_esc_key(self) -> None:
        """Esc: dismiss modal / find / menu, or open the menu when idle.

        App-level priority so the editor cannot swallow Esc. Context decides
        whether Esc means “back” or “summon menu”.
        """
        # Modal screens (path prompt, confirm, …) — run their cancel if any.
        if len(self.screen_stack) > 1:
            screen = self.screen
            for name in ("action_cancel", "action_dismiss", "action_close"):
                action = getattr(screen, name, None)
                if callable(action):
                    action()
                    return
            return

        try:
            find = self.query_one("#find-bar", FindBar)
            if find.is_visible:
                find.hide()
                return
        except Exception:
            pass

        try:
            menu = self.query_one("#app-menu", MenuBar)
            if menu.is_open:
                menu.close_menu()
                return
        except Exception:
            pass

        self._toggle_menu(None)

    def on_key(self, event: Key) -> None:
        """Hard fallback: some terminals drop priority bindings while TextArea is focused."""
        try:
            menu = self.query_one("#app-menu", MenuBar)
            if menu.is_open:
                return
        except Exception:
            pass
        key = normalize_key(event.key)
        if key == "escape":
            event.stop()
            self.action_esc_key()
            return
        if key == "f9" or key == "ctrl+shift+p":
            event.stop()
            self._toggle_menu(None)
            return
        # Find/replace fallbacks when focus ate the binding.
        if key in {"ctrl+r", "ctrl+h"}:
            # Never treat Backspace as replace — only a true ctrl+h key name.
            event.stop()
            self.cmd_replace()
            return
        if key == "ctrl+enter":
            event.stop()
            self.cmd_find_prev()
            return
        if is_replace_all_key(key):
            event.stop()
            self.cmd_replace_all()
            return
        # Bulk file ops (Alt order / case variants).
        if key in {"ctrl+alt+s", "alt+ctrl+s"}:
            event.stop()
            self.cmd_save_all()
            return
        if key in {"ctrl+shift+s"}:
            event.stop()
            self.cmd_save_as()
            return
        if key in {"ctrl+o"}:
            event.stop()
            self.cmd_open_file()
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

    def _toggle_menu(self, menu_name: str | None) -> None:
        """Open or close the in-layout top-line menu bar."""
        try:
            bar = self.query_one("#app-menu", MenuBar)
        except Exception as exc:
            self.notify(f"Could not open menu: {exc}", severity="error")
            return
        if bar.is_open:
            bar.close_menu()
            return
        try:
            bar.open_menu(menu_name)
        except Exception as exc:
            self.notify(f"Could not open menu: {exc}", severity="error")

    @on(MenuBar.CommandChosen)
    def _on_menu_command(self, event: MenuBar.CommandChosen) -> None:
        try:
            self.registry.execute(event.command_id)
        except Exception as exc:
            self.notify(f"Command failed: {exc}", severity="error")

    @on(MenuBar.Closed)
    def _on_menu_closed(self, event: MenuBar.Closed) -> None:
        try:
            self.query_one("#editor", TextArea).focus()
        except Exception:
            pass

    def cmd_new_file(self) -> None:
        self._sync_document_from_editor()
        self.workspace.new_document()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        self.notify("New file")

    def cmd_open_file(self) -> None:
        """Open a path via prompt (file dialog later)."""
        self.run_worker(self._open_file_async())

    def action_open_file(self) -> None:
        self.cmd_open_file()

    async def _open_file_async(self) -> None:
        raw = await self.push_screen_wait(
            _PathPrompt(
                "Open — enter a file path",
                initial=str(Path.cwd()) + "/",
                hint="Enter open · Esc cancel · ~ allowed · missing path creates empty tab",
            )
        )
        if raw is None:
            return
        path = self._normalize_save_path(raw)
        if path is None:
            self.notify("Empty path — nothing opened", severity="warning")
            return
        self._sync_document_from_editor()
        try:
            self.workspace.open_path(path)
        except OSError as exc:
            self.notify(f"Open failed: {exc}", severity="error")
            return
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        if path.exists():
            self.notify(f"Opened {path}")
        else:
            self.notify(f"New buffer for {path} (not on disk yet)")

    def cmd_close(self) -> None:
        self._sync_document_from_editor()
        was_dirty = self.document.dirty
        self.workspace.close_active()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        if was_dirty:
            self.notify("Closed tab (unsaved buffer discarded)", severity="warning")

    def cmd_close_others(self) -> None:
        """Close every tab except the active one. Confirm if others are dirty."""
        self._sync_document_from_editor()
        if self.workspace.count <= 1:
            self.notify("No other tabs to close")
            return

        others_dirty = [
            doc
            for i, doc in enumerate(self.workspace.documents)
            if i != self.workspace.active_index and doc.dirty
        ]
        if not others_dirty:
            self._do_close_others()
            return

        names = [doc.path.name if doc.path else "Untitled" for doc in others_dirty]
        listed = ", ".join(names[:4]) + ("…" if len(names) > 4 else "")
        detail = (
            f"{len(names)} other tab(s) have unsaved changes ({listed})."
            if len(names) > 1
            else f'"{names[0]}" has unsaved changes.'
        )

        async def _confirm() -> None:
            ok = await self.push_screen_wait(
                _ConfirmDialog(
                    title="Close other tabs?",
                    message=detail + "\nClose others and discard their unsaved work?",
                    yes_label="close others",
                    no_label="stay",
                )
            )
            if ok:
                self._do_close_others()

        self.run_worker(_confirm())

    def action_close_others(self) -> None:
        self.cmd_close_others()

    def _do_close_others(self) -> None:
        self._sync_document_from_editor()
        closed = self.workspace.count - 1
        self.workspace.close_others()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        self.notify(f"Closed {closed} other tab(s)")

    def cmd_close_all(self) -> None:
        """Close every tab (leave one empty). Menu-only; confirm if dirty."""
        dirty = self._unsaved_documents()
        if not dirty:
            self._do_close_all()
            return

        names = [doc.path.name if doc.path else "Untitled" for doc in dirty]
        if len(names) == 1:
            detail = f'"{names[0]}" has unsaved changes.'
        else:
            listed = ", ".join(names[:4]) + ("…" if len(names) > 4 else "")
            detail = f"{len(names)} tabs have unsaved changes ({listed})."

        async def _confirm() -> None:
            ok = await self.push_screen_wait(
                _ConfirmDialog(
                    title="Close all tabs?",
                    message=detail + "\nClose all and discard unsaved work?",
                    yes_label="close all",
                    no_label="stay",
                )
            )
            if ok:
                self._do_close_all()

        self.run_worker(_confirm())

    def _do_close_all(self) -> None:
        self._sync_document_from_editor()
        n = self.workspace.count
        self.workspace.close_all()
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        self.notify(f"Closed {n} tab(s)")

    def cmd_save_all(self) -> None:
        """Save every dirty tab. Untitled tabs get a path prompt each."""
        self.run_worker(self._save_all_async())

    def action_save_all(self) -> None:
        self.cmd_save_all()

    async def _save_all_async(self) -> None:
        # Flush the focused editor into its Document first.
        self._sync_document_from_editor()
        saved = 0
        skipped = 0
        errors = 0
        resume_index = self.workspace.active_index

        dirty_indices = [
            i for i, doc in enumerate(self.workspace.documents) if doc.dirty
        ]
        if not dirty_indices:
            self.notify("Nothing to save (no dirty tabs)")
            return

        for i in dirty_indices:
            if i >= self.workspace.count:
                continue
            doc = self.workspace.documents[i]
            if doc.path is not None:
                # Save straight from the Document — do not round-trip the
                # TextArea (load_text can race and clobber another tab's buffer).
                try:
                    doc.save()
                    saved += 1
                except OSError as exc:
                    errors += 1
                    self.notify(
                        f"Save failed ({doc.path.name}): {exc}",
                        severity="error",
                    )
                continue

            # Untitled dirty — switch so the path prompt names this buffer.
            self.workspace.set_active(i)
            self._load_active_into_editor()
            self._refresh_status()
            ok = await self._prompt_and_save_async(
                title=f"Save All — name for untitled tab {i + 1}",
                initial=str(Path.cwd() / "untitled.md"),
            )
            if ok:
                saved += 1
            else:
                skipped += 1

        # Restore the tab the user was on.
        if resume_index < self.workspace.count:
            self.workspace.set_active(resume_index)
        self._load_active_into_editor()
        self._refresh_status()
        parts = [f"Saved {saved}"]
        if skipped:
            parts.append(f"{skipped} skipped")
        if errors:
            parts.append(f"{errors} failed")
        self.notify(", ".join(parts))

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
            self.run_worker(
                self._prompt_and_save_async(
                    title="Save — where should this file go?",
                    initial=str(Path.cwd() / "untitled.md"),
                )
            )
            return
        self._write_active_document()

    def cmd_save_as(self) -> None:
        """Save active buffer under a new path (always prompts)."""
        self._sync_document_from_editor()
        initial = (
            str(self.document.path)
            if self.document.path is not None
            else str(Path.cwd() / "untitled.md")
        )
        self.run_worker(
            self._prompt_and_save_async(
                title="Save As — enter a path",
                initial=initial,
            )
        )

    def action_save_as(self) -> None:
        self.cmd_save_as()

    def _write_active_document(self, path: Path | None = None) -> bool:
        """Write active buffer. Returns True on success."""
        try:
            self.document.save(path)
            self.notify(f"Saved {self.document.path}")
            self._refresh_status()
            return True
        except OSError as exc:
            self.notify(f"Save failed: {exc}", severity="error")
            return False
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return False

    def _prompt_and_save(self, *, title: str, initial: str = "") -> None:
        """Fire-and-forget path prompt + save (legacy wrapper)."""
        self.run_worker(self._prompt_and_save_async(title=title, initial=initial))

    async def _prompt_and_save_async(self, *, title: str, initial: str = "") -> bool:
        """Ask for a path, confirm overwrite if needed, save. True if written."""
        raw = await self.push_screen_wait(
            _PathPrompt(
                title,
                initial=initial or str(Path.cwd() / "untitled.md"),
                hint="Enter path · Enter save · Esc cancel · ~ allowed",
            )
        )
        if raw is None:
            return False
        path = self._normalize_save_path(raw)
        if path is None:
            self.notify("Empty path — not saved", severity="warning")
            return False

        # Overwrite guard: existing file that isn't this buffer's current path.
        if path.exists():
            same = (
                self.document.path is not None
                and path.resolve() == self.document.path.resolve()
            )
            if not same:
                ok = await self.push_screen_wait(
                    _ConfirmDialog(
                        title="Overwrite existing file?",
                        message=(
                            f'"{path}" already exists.\n'
                            "Overwrite it with this buffer?"
                        ),
                        yes_label="overwrite",
                        no_label="cancel",
                    )
                )
                if not ok:
                    self.notify("Save cancelled", severity="information")
                    return False

        return self._write_active_document(path)

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
                _ConfirmDialog(
                    title="Quit Prose?",
                    message=detail + "\nQuit anyway and discard unsaved work?",
                    yes_label="quit",
                    no_label="stay",
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
        self._open_find(replace=False)

    def cmd_replace(self) -> None:
        self._open_find(replace=True)

    def action_show_replace(self) -> None:
        self.cmd_replace()

    def action_replace_one_key(self) -> None:
        self.cmd_replace_one()

    def action_replace_all_key(self) -> None:
        self.cmd_replace_all()

    def cmd_find_next(self) -> None:
        self._find_direction("next")

    def cmd_find_prev(self) -> None:
        self._find_direction("prev")

    def action_find_next(self) -> None:
        self.cmd_find_next()

    def action_find_prev(self) -> None:
        self.cmd_find_prev()

    def _open_find(self, *, replace: bool) -> None:
        """Show find (or replace) bar; seed from single-line selection if any.

        If find is already open and the user asks for replace, expand in place
        (keep the find string, show the replace row, focus replace field).
        """
        bar = self.query_one("#find-bar", FindBar)

        # Already open: expand / refocus without wiping the find string.
        if bar.is_visible:
            if replace:
                if not bar.is_replace_mode:
                    bar.expand_replace()
                else:
                    bar.query_one("#replace-input").focus()
                if bar.query:
                    self._update_find_count()
                return
            # Ctrl+F while open: focus find field (keep replace row if shown).
            bar.query_one("#find-input").focus()
            return

        editor = self.query_one("#editor", TextArea)
        seed: str | None = None
        try:
            selected = editor.selected_text
        except Exception:
            selected = ""
        if selected and "\n" not in selected and len(selected) < 200:
            seed = selected
        bar.show(replace=replace, seed=seed)
        if bar.query:
            # Jump to first match from caret without requiring Enter first.
            self._find_direction("next", announce_missing=False)
            self._update_find_count()

    @on(FindBar.ExpandReplace)
    def _on_expand_replace(self, event: FindBar.ExpandReplace) -> None:
        # FindBar already expanded; keep highlights/count in sync.
        try:
            bar = self.query_one("#find-bar", FindBar)
        except Exception:
            return
        if bar.query:
            self._update_find_count()

    def cmd_replace_one(self) -> None:
        self._sync_document_from_editor()
        bar = self.query_one("#find-bar", FindBar)
        if not bar.is_visible or not bar.is_replace_mode:
            self.cmd_replace()
            return
        query = bar.query
        if not query:
            self.notify("Enter a find string", severity="warning")
            return
        cursor = self._cursor_index()
        # Prefer replacing the current selection if it is exactly the match.
        editor = self.query_one("#editor", TextArea)
        try:
            selected = editor.selected_text
        except Exception:
            selected = ""
        match = None
        if selected and selected.lower() == query.lower():
            # Selection is the match — use its span.
            start = self._selection_start_index()
            if start is not None:
                match = Match(start, start + len(selected))
        if match is None:
            match = find_next(self.document.text, query, start=cursor)
        if match is None:
            match = find_next(self.document.text, query, start=0)
        if match is None:
            self.notify(f"Not found: {query!r}", severity="warning")
            self._update_find_count()
            return
        new_m = replace_match(self.document, match, bar.replacement)
        self._push_document_to_editor()
        self._last_find_end = new_m.end
        # Advance to the next occurrence after the replacement.
        nxt = find_next(self.document.text, query, start=new_m.end)
        if nxt is None and new_m.end > 0:
            nxt = find_next(self.document.text, query, start=0)
        if nxt is not None:
            self._select_range(nxt.start, nxt.end)
            self._last_find_end = nxt.end
        else:
            self._select_range(new_m.start, new_m.end)
        self._refresh_status()
        self._update_find_count()

    def cmd_replace_all(self) -> None:
        """Replace every match of the find string with the replace field.

        Opens the replace bar if needed. Requires a non-empty find string;
        empty replacement is allowed (delete all matches).
        """
        self._sync_document_from_editor()
        bar = self.query_one("#find-bar", FindBar)
        if not bar.is_visible:
            self.cmd_replace()
            # User still needs a find string; don't replace blindly.
            if not bar.query:
                self.notify("Enter a find string, then Ctrl+Alt+R for replace all", severity="warning")
                return
        elif not bar.is_replace_mode:
            bar.expand_replace()
        query = bar.query
        if not query:
            self.notify("Enter a find string", severity="warning")
            return
        n = replace_all(self.document, query, bar.replacement)
        self._push_document_to_editor()
        self._last_find_end = 0
        self._refresh_status()
        self._update_find_count()
        self.notify(f"Replaced {n} occurrence(s)")

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
        try:
            self.query_one("#editor", ProseTextArea).clear_search_highlights()
        except Exception:
            pass
        self.query_one("#editor", TextArea).focus()

    @on(FindBar.ReplaceRequested)
    def _on_replace_requested(self, event: FindBar.ReplaceRequested) -> None:
        if event.mode == "all":
            self.cmd_replace_all()
        else:
            self.cmd_replace_one()

    @on(FindBar.QueryChanged)
    def _on_find_query_changed(self, event: FindBar.QueryChanged) -> None:
        self._last_find_end = 0
        self._update_find_count()
        if event.query:
            self._find_direction("next", announce_missing=False)
        else:
            self._refresh_search_highlights()

    def _selection_start_index(self) -> int | None:
        editor = self.query_one("#editor", TextArea)
        try:
            start_loc = editor.selection.start
            end_loc = editor.selection.end
            # Normalize so "start" is the lower index (selection can be reversed).
            a = int(editor.document.get_index_from_location(start_loc))
            b = int(editor.document.get_index_from_location(end_loc))
            return min(a, b)
        except Exception:
            return None

    def _refresh_search_highlights(self) -> None:
        """Soft-highlight every match; focused one stays bright via selection."""
        try:
            editor = self.query_one("#editor", ProseTextArea)
            bar = self.query_one("#find-bar", FindBar)
        except Exception:
            return
        if not bar.is_visible or not bar.query:
            editor.clear_search_highlights()
            return
        self._sync_document_from_editor()
        matches = find_all(self.document.text, bar.query)
        editor.set_search_highlights(matches)

    def _update_find_count(self) -> None:
        """Refresh the ``n/total`` badge on the find bar and soft highlights."""
        try:
            bar = self.query_one("#find-bar", FindBar)
        except Exception:
            return
        if not bar.is_visible:
            self._refresh_search_highlights()
            return
        query = bar.query
        if not query:
            bar.set_match_count(None, 0)
            self._refresh_search_highlights()
            return
        self._sync_document_from_editor()
        matches = find_all(self.document.text, query)
        total = len(matches)
        # Keep editor paint in lockstep with the counter.
        try:
            self.query_one("#editor", ProseTextArea).set_search_highlights(matches)
        except Exception:
            pass
        if total == 0:
            bar.set_match_count(None, 0)
            return
        # 1-based index of match that starts at/near the current selection start.
        cursor = self._cursor_index()
        current: int | None = None
        for i, m in enumerate(matches):
            if m.start <= cursor < m.end or m.start == cursor or (
                self._last_find_end and m.end == self._last_find_end
            ):
                current = i + 1
                break
        if current is None and self._last_find_end:
            for i, m in enumerate(matches):
                if m.end == self._last_find_end:
                    current = i + 1
                    break
        bar.set_match_count(current, total)

    def _find_direction(
        self,
        direction: str,
        *,
        announce_missing: bool = True,
    ) -> None:
        self._sync_document_from_editor()
        bar = self.query_one("#find-bar", FindBar)
        query = bar.query
        if not query:
            if announce_missing:
                self.notify("Enter a find string", severity="warning")
            if not bar.is_visible:
                bar.show(replace=False)
            return

        text = self.document.text
        cursor = self._cursor_index()

        # Prefer the start of the currently selected match as the step origin.
        current_start: int | None = None
        try:
            selected = self.query_one("#editor", TextArea).selected_text
        except Exception:
            selected = ""
        if selected and selected.lower() == query.lower():
            current_start = self._selection_start_index()
        if current_start is None and self._last_find_end:
            # Reconstruct start from last focused end + query length.
            current_start = max(0, self._last_find_end - len(query))

        match = step_find(
            text,
            query,
            direction=direction,
            cursor=cursor,
            current_start=current_start,
        )

        if match is None:
            if announce_missing:
                self.notify(f"Not found: {query!r}", severity="warning")
            self._update_find_count()
            return

        self._last_find_end = match.end
        self._select_range(match.start, match.end)
        self._update_find_count()


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


class _ConfirmDialog(ModalScreen[bool]):
    """Yes/No confirm. True = yes, False = no/cancel."""

    CSS = """
    _ConfirmDialog {
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
            yield Label(
                f"[#007ACC]Y[/]/Enter {self._yes_label}  ·  "
                f"[#007ACC]N[/]/Esc {self._no_label}",
                id="confirm-hint",
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

"""MarkStar TUI entrypoint (P0 shell + P1 commands / menus / find)."""

from __future__ import annotations

import argparse
import inspect
import asyncio
import re
import sys
from functools import partial
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual import events
from textual.geometry import Size
from textual.widgets import Static, TextArea
from textual.widgets.text_area import Selection

from markstar import __version__
from markstar.commands.registry import Command, CommandRegistry
from markstar.config import (
    RECENT_FILES_MAX,
    RECENT_PROJECTS_MAX,
    Preferences,
    session_path,
)
from markstar.domain.session import OpenFile, Session
from markstar.domain.session import load as session_load
from markstar.domain.session import save as session_save
from markstar.domain.document import Document
from markstar.domain import wordcount
from markstar.domain.export import export as export_document
from markstar.domain.recent import prune_missing, push_recent
from markstar.domain.wordcount import Counts
from markstar.domain.savepath import resolve_save_path
from markstar.domain.motion import paragraph_down, paragraph_up, word_left, word_right
from markstar.domain.autosave import (
    delete_sidecar,
    read_sidecar,
    sidecar_is_newer,
    write_sidecar,
)
from markstar.domain.includes import compile_document, make_resolver
from markstar.domain.markdown import (
    RE_BOLD,
    RE_CODE,
    RE_FENCE,
    RE_ITALIC,
    RE_LINK,
    RE_STRIKE,
    markdown_spans,
    toggle_emphasis,
    word_bounds,
)
from markstar.domain.spellcheck import Speller
from markstar.domain.workspace import Workspace
from markstar.ui.dialogs import (
    ConfirmDialog,
    PathPrompt,
    RestoreDialog,
    SaveChangesDialog,
)
from markstar.domain.outline import headings as md_headings
from markstar.domain.projectsearch import search_project
from markstar.ui.export_dialog import ExportDialog
from markstar.ui.find_results import FindResultsScreen
from markstar.ui.help_screen import HelpScreen
from markstar.ui.outline import OutlineScreen
from markstar.ui.quick_open import QuickOpenScreen
from markstar.ui.edit_card import EditCard
from markstar.ui.editor_session import EditorSession
from markstar.ui.layout import PANEL_GAP, ProseLayout, compute_layout
from markstar.ui.starbot_panel import StarBotPanel
from markstar.ui.scrollbar import install as _install_thin_scrollbars
from markstar.ui.tab_bar import TabBar, TabInfo

_install_thin_scrollbars()  # slimmer scrollbar glyph, process-wide
from markstar.ui.find_bar import FindBar
from markstar.ui.find_controller import FindController
from markstar.ui.keys import normalize_key
from markstar.ui.menu_bar import MenuBar
from markstar.ui.project_panel import ProjectPanel, WriterTree, is_openable
from markstar.ui.spell_bar import SpellBar
from markstar.ui.spell_controller import SpellController
from markstar.ui.starbot_config import StarBotConfigScreen
from markstar.ui.theme_picker import ThemePicker
from markstar.ui.welcome import WelcomeScreen
from markstar.ui.themes import (
    ALL_THEMES,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    token,
)

# Inline Markdown parsing/editing lives in domain/markdown.py (pure, testable).
# See docs/MARKSTAR_KEYMAP.md §5b for the "style spans, never hide characters"
# approach that keeps document columns 1:1 with screen columns.

# Prose-layout geometry constants + compute_layout() live in ui/layout.py.
# Footer metrics compaction thresholds (see _refresh_metrics).
_METRICS_NARROW = 66          # below: drop the least-important metric
_METRICS_MEDIUM = 92          # below: compact labels
# Debounce before recounting prose. Long enough that a burst of typing costs
# one pass, short enough that the footer feels live when you stop.
_METRICS_DEBOUNCE = 0.35
# (Spell suggestion popup sizing lives in ui/suggest_popup.)
# Terminal control (OSC): set/reset the default background so the sub-cell strip
# below the last row matches the theme instead of the terminal default.
_OSC_SET_BG = "\x1b]11;{bg}\x07"
_OSC_RESET_BG = "\x1b]111\x07"
# File-naming.
_DEFAULT_SUFFIX = ".md"
_COMPILED_SUFFIX = ".compiled.md"

# Tab-chip geometry + rendering now live in ui/tab_bar.TabBar.


class MarkStarTextArea(TextArea):
    """MarkStar editing surface.

    Narrows the soft-wrap width so text keeps a 5-column right margin while
    the widget itself (and its scrollbar) runs flush to the window edge. Right
    padding can't do this: Textual carves the scrollbar out of the region left
    over AFTER padding, so padding-right insets the scrollbar as well.

    Rendering: ``get_line`` paints (a) inline Markdown formatting — bold/italic/
    code/headings styled in place with markers dimmed — and (b) search-match
    backgrounds. Both use theme color tokens (see ``prose.ui.themes``), so a
    theme change repaints them. Toggle formatting with ``render_markdown``.
    """

    # Base wrap_width already reserves the scrollbar column + 1 cursor cell, so
    # text runs flush to the scrollbar with no extra right inset. (Was 3, which
    # left a visible gap between the wrapped text and the edge.)
    EXTRA_RIGHT_MARGIN = 0

    # Textual's TextArea binds Home/End to the *line* ends and never binds the
    # Ctrl variants, so document-start/end simply did nothing. In a manuscript
    # that is the difference between reaching chapter one and scrolling to it.
    # (No Ctrl+Shift+Home/End companions: terminals can't be relied on to send
    # them, and a shortcut that works on one machine only is worse than none.)
    BINDINGS = [
        Binding("ctrl+home", "cursor_doc_start", "Top of document", show=False),
        Binding("ctrl+end", "cursor_doc_end", "End of document", show=False),
    ]

    def action_cursor_doc_start(self) -> None:
        self.move_cursor((0, 0))
        self.scroll_cursor_visible()

    def action_cursor_doc_end(self) -> None:
        last = self.document.line_count - 1
        self.move_cursor((last, len(self.document.get_line(last))))
        self.scroll_cursor_visible()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # line_index -> list of (start_col, end_col) character offsets on that line
        self._search_by_line: dict[int, list[tuple[int, int]]] = {}
        self._spell_by_line: dict[int, list[tuple[int, int]]] = {}
        self.render_markdown = True
        self._styles: dict[str, Style] = {}
        self._style_key: str | None = None  # theme name the cache was built for
        # line_index -> "fence" (a ``` delimiter line) | "code" (line inside a fence)
        self._fence_lines: dict[int, str] = {}
        self.prose_width = 0  # 0 = no cap; else max writing-measure columns
        self.scroll_past_end = True  # extra room below the last line (see below)

    # Fraction of the viewport left empty below the last line at max scroll, so
    # the final line can rest ~1/3 of the way down (2/3 empty) — "typewriter room".
    _SCROLL_PAST_END_FRACTION = 2 / 3

    def _refresh_size(self) -> None:
        """Extend the scrollable area below the document so the last line can be
        scrolled up to ~1/3 of the screen height (2/3 empty below), instead of
        sticking to the bottom edge. Only engages once the document actually
        overflows the viewport, so short files don't gain a phantom scrollbar."""
        super()._refresh_size()
        if not getattr(self, "scroll_past_end", False):
            return
        view = self.size.height
        # Base the extra on the true content height (wrapped_document.height), NOT
        # the post-super virtual_size — reading the latter back can compound the
        # padding across the re-layouts that enlarging virtual_size triggers.
        content_h = self.wrapped_document.height
        if view > 0 and content_h > view:
            extra = int(view * self._SCROLL_PAST_END_FRACTION)
            self.virtual_size = Size(self.virtual_size.width, content_h + extra)

    @property
    def wrap_width(self) -> int:
        width = super().wrap_width
        width = max(0, width - self.EXTRA_RIGHT_MARGIN) if width else width
        # getattr: wrap_width is read during super().__init__, before our attr set.
        cap = getattr(self, "prose_width", 0)
        if cap and width > cap:
            width = cap
        return width

    def _theme_styles(self) -> dict[str, Style]:
        """Rich styles for each span kind, resolved from the current theme."""
        name = getattr(self.app, "theme", None)
        if name == self._style_key and self._styles:
            return self._styles
        marker = token(self.app, "md-marker")
        self._styles = {
            "marker": Style(color=marker),
            "strong": Style(color=token(self.app, "md-strong"), bold=True),
            "emphasis": Style(color=token(self.app, "md-emphasis"), italic=True),
            "code": Style(color=token(self.app, "md-code")),
            "strike": Style(color=marker, strike=True),
            "heading": Style(color=token(self.app, "md-heading"), bold=True),
            "quote": Style(color=token(self.app, "md-quote"), italic=True),
            "link": Style(color=token(self.app, "md-link"), underline=True),
            "include": Style(color=token(self.app, "md-include"), bold=True),
            "search": Style(bgcolor=token(self.app, "search-match")),
            "spell": Style(
                color=token(self.app, "spell-underline"), underline=True
            ),
        }
        self._style_key = name
        return self._styles

    def recompute_fences(self) -> None:
        """Map each line to fenced-code state. Call after any text change.

        Fenced blocks span multiple lines, so per-line ``get_line`` can't detect
        them alone — we scan the whole document and toggle in/out on ``` lines.
        """
        fences: dict[int, str] = {}
        in_fence = False
        for i, line in enumerate(self.text.split("\n")):
            if RE_FENCE.match(line):
                fences[i] = "fence"
                in_fence = not in_fence
            elif in_fence:
                fences[i] = "code"
        if fences != self._fence_lines:
            self._fence_lines = fences
            self._line_cache.clear()
            self.refresh()

    def load_text(self, text: str) -> None:  # type: ignore[override]
        super().load_text(text)
        self.recompute_fences()

    def set_render_markdown(self, on: bool) -> None:
        self.render_markdown = on
        self._line_cache.clear()
        self.refresh()

    def refresh_theme_styles(self) -> None:
        """Drop the style cache so the next paint picks up a new theme."""
        self._style_key = None
        self._line_cache.clear()
        self.refresh()

    def action_paste(self) -> None:
        """Ctrl+V: paste the OS clipboard (so text copied in other apps works),
        falling back to Textual's internal clipboard when no native tool exists.
        """
        native = self.app._native_clipboard_paste()  # type: ignore[attr-defined]
        if native is not None:
            self.app._clipboard = native  # what super().action_paste() reads
        super().action_paste()

    def _location_over_link(self, event: events.MouseMove) -> bool:
        """True if the mouse is over a ``[text](url)`` span."""
        try:
            row, col = self.get_target_document_location(event)
            line = self.document.get_line(row)
        except Exception:
            return False
        return any(m.start() <= col < m.end() for m in RE_LINK.finditer(line))

    def on_click(self, event: events.Click) -> None:
        """Single click = place caret (TextArea default); double = select word;
        triple = select line. Uses the click ``chain`` count."""
        if event.chain < 2:
            return
        try:
            row, col = self.get_target_document_location(event)
        except Exception:
            return
        if event.chain == 2:
            line = self.document.get_line(row)
            a, b = word_bounds(line, col)
            if a != b:
                self.selection = Selection((row, a), (row, b))
                event.stop()
        else:  # triple (or more) → whole line
            self.select_line(row)
            event.stop()

    async def _on_mouse_move(self, event: events.MouseMove) -> None:
        await super()._on_mouse_move(event)
        # Hand pointer over links, typewriter caret over the rest of the text.
        want = "pointer" if (self.render_markdown and self._location_over_link(event)) else "text"
        try:
            if self.styles.pointer != want:
                self.styles.pointer = want
        except Exception:
            pass

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

    def set_spell_highlights(self, matches: list[Match]) -> None:
        """Underline misspelled words. Pass ``[]`` to clear."""
        by_line: dict[int, list[tuple[int, int]]] = {}
        for match in matches:
            try:
                sr, sc = self.document.get_location_from_index(match.start)
                er, ec = self.document.get_location_from_index(match.end)
            except Exception:
                continue
            if sr == er:
                by_line.setdefault(sr, []).append((sc, ec))
        if by_line == self._spell_by_line:
            return
        self._spell_by_line = by_line
        self._line_cache.clear()
        self.refresh()

    def clear_spell_highlights(self) -> None:
        if not self._spell_by_line:
            return
        self._spell_by_line = {}
        self._line_cache.clear()
        self.refresh()

    def get_line(self, line_index: int) -> Text:
        line = super().get_line(line_index)
        styles: dict[str, Style] | None = None

        if self.render_markdown:
            text = line.plain
            fence_kind = self._fence_lines.get(line_index)
            if fence_kind == "fence":
                # The ``` delimiter line itself — dim it like a marker.
                styles = self._theme_styles()
                line.stylize(styles["marker"], 0, len(text))
            elif fence_kind == "code":
                # A content line inside a fenced block — whole line as code.
                styles = self._theme_styles()
                line.stylize(styles["code"], 0, len(text))
            else:
                md_spans = markdown_spans(text)
                if md_spans:
                    styles = self._theme_styles()
                    length = len(text)
                    for start, end, kind in md_spans:
                        if 0 <= start < end <= length:
                            line.stylize(styles[kind], start, end)

        search = self._search_by_line.get(line_index)
        if search:
            if styles is None:
                styles = self._theme_styles()
            for start_col, end_col in search:
                if start_col < end_col:
                    line.stylize(styles["search"], start_col, end_col)

        spell = self._spell_by_line.get(line_index)
        if spell:
            if styles is None:
                styles = self._theme_styles()
            for start_col, end_col in spell:
                if start_col < end_col:
                    line.stylize(styles["spell"], start_col, end_col)
        return line


class MarkStarApp(App[None]):
    """Writing shell with command registry, menus, and find/replace."""

    TITLE = "MarkStar"
    # Disable Textual's built-in command palette — we use a classic menu ribbon.
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }

    /* Text-entry areas get the I-beam / typewriter mouse pointer (OSC 22;
       honored by terminals that support pointer shapes, ignored otherwise). */
    Input {
        pointer: text;
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
       right text inset comes from MarkStarTextArea.wrap_width instead. scrollbar-gutter:
       stable reserves the bar column even when the document fits, keeping the wrap
       column identical whether or not the bar is drawn. */
    #editor-row {
        height: 1fr;
        width: 100%;
        background: $background;
        /* Project panel overlays the left of this band without shifting prose. */
        layers: base overlay;
    }

    #editor-left-pad, #editor-right-pad {
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
           MarkStarTextArea.wrap_width so the scrollbar stays flush at the window edge. */
        padding: 0;
        /* Typewriter caret over the writing surface; the mouse-move handler flips
           this to a hand when hovering a Markdown link. */
        pointer: text;
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

    # Menu: Esc is primary (Word/Works-style). F9 is the alternate.
    # Esc also dismisses find/modals when those are open (see action_esc_key).
    # Everything else is bound from the command registry in on_mount(); only the
    # menu keys and cursor motion (which must beat TextArea's own bindings) live
    # here. See docs/MARKSTAR_KEYMAP.md — no Ctrl+Shift, no chords, all portable.
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
        # Tab cycling has two routes on purpose. F6 / Shift+F6 are the primary
        # pair: a bare F-key is one unambiguous escape sequence no terminal
        # rewrites, and F6 is CUA's "next pane/window" — what Works meant by
        # Ctrl+F6. Ctrl+PageUp/PageDown stay as aliases for terminals that pass
        # them through; VTE terminals (GNOME Terminal) bind those to their own
        # tabs, so they never reach us there. If Shift+F6 is the one that goes
        # missing, plain F6 still wraps around to every tab.
        Binding("ctrl+pagedown", "next_tab", "Next tab", show=False, priority=True),
        Binding("ctrl+pageup", "prev_tab", "Previous tab", show=False, priority=True),
        Binding("ctrl+right", "word_right", "Word right", show=False, priority=True),
        Binding("ctrl+left", "word_left", "Word left", show=False, priority=True),
        Binding("ctrl+up", "paragraph_up", "Paragraph up", show=False, priority=True),
        Binding("ctrl+down", "paragraph_down", "Paragraph down", show=False, priority=True),
        # Ctrl+C is COPY, never quit. This overrides Textual's app-level
        # "help_quit" binding (which pops a "Do you want to quit?" toast when
        # focus isn't on a text widget). Quit lives on Ctrl+Q alone.
        Binding("ctrl+c", "smart_copy", "Copy", show=False, priority=True),
    ]

    def __init__(
        self, path: Path | None = None, prefs: Preferences | None = None
    ) -> None:
        super().__init__()
        self.prefs = prefs or Preferences()
        for _theme in ALL_THEMES:
            self.register_theme(_theme)
        self.theme = self.prefs.theme  # validated to a known theme on load
        self._path_arg = path
        self.workspace = Workspace()
        # Owns the Document <-> editor text invariant (see EditorSession). Fetches
        # the editor lazily since it isn't mounted until compose runs.
        self._session = EditorSession(
            self.workspace, lambda: self.query_one("#editor", TextArea)
        )
        self.registry = CommandRegistry()
        self._find = FindController(
            get_editor=lambda: self.query_one("#editor", MarkStarTextArea),
            get_bar=lambda: self.query_one("#find-bar", FindBar),
            get_document=lambda: self.document,
            cursor_index=self._cursor_index,
            select_range=self._select_range,
            selection_start_index=self._selection_start_index,
            notify=self.notify,
            push_editor=self._push_document_to_editor,
            refresh_status=self._refresh_status,
        )
        self._spell = SpellController(
            prefs=self.prefs,
            get_editor=lambda: self.query_one("#editor", MarkStarTextArea),
            get_bar=lambda: self.query_one("#spell-bar", SpellBar),
            get_document=lambda: self.document,
            select_range=self._select_range,
            # Late-bound so tests that patch these on the app still take effect.
            notify=lambda *a, **k: self.notify(*a, **k),
            set_timer=lambda *a, **k: self.set_timer(*a, **k),
            run_worker=lambda *a, **k: self.run_worker(*a, **k),
            call_from_thread=lambda *a, **k: self.call_from_thread(*a, **k),
            push_screen_wait=lambda *a, **k: self.push_screen_wait(*a, **k),
            screen_size=lambda: self.size,
        )
        self._autosave_timer = None
        # Prose-count cache + debounce — see _refresh_metrics.
        self._counts_text: str | None = None
        self._counts = Counts(0, 0)
        self._sel_range = None
        self._sel_words = 0
        self._counts_timer = None
        # path -> (row, col), so a tab reopens where you left it.
        self._caret_memory: dict[str, tuple[int, int]] = {}
        self._starbot_chat = None  # ai.chat.StarBotChat, built lazily on first use
        self._starbot_transcript = None  # ai.history.ChatTranscript for the session
        self._starbot_proposals = {}  # proposal id -> (EditProposal, EditCard)
        self._build_commands()

    # Compat accessors so callers/tests keep reaching the speller + walk state.
    @property
    def _speller(self) -> Speller:
        return self._spell.speller

    @property
    def _spell_current(self):
        return self._spell.current

    @property
    def document(self) -> Document:
        # Auto-flushes the editor's live text into the active Document, so every
        # command reads fresh text without a manual pre-sync. See EditorSession.
        return self._session.document

    def _project_root(self) -> Path:
        """Root folder for the project panel: the opened file's dir, or cwd."""
        if self._path_arg is not None:
            try:
                return self._path_arg if self._path_arg.is_dir() else self._path_arg.parent
            except OSError:
                pass
        return Path.cwd()

    def _record_recent_project(self, root: Path) -> None:
        """Push a folder to the front of the recent-projects list."""
        self.prefs.recent_projects = push_recent(
            self.prefs.recent_projects, root, RECENT_PROJECTS_MAX
        )
        self.prefs.save()

    def _record_recent_file(self, path: Path) -> None:
        """Push a document to the front of the recent-files list."""
        self.prefs.recent_files = push_recent(
            self.prefs.recent_files, path, RECENT_FILES_MAX
        )
        self.prefs.save()

    def _recent_files(self) -> list[str]:
        """Recent documents that still exist, pruning any that don't.

        Pruning at read (rather than on a filesystem watch) keeps the list
        honest without any background work: a renamed file simply stops being
        offered the next time something asks.
        """
        kept = prune_missing(self.prefs.recent_files)
        if kept != self.prefs.recent_files:
            self.prefs.recent_files = kept
            self.prefs.save()
        return kept

    def _infer_project_root(self, path: Path) -> Path:
        """Best project folder for a file: its deepest known recent project.

        Mirrors what ``markstar <folder>/file.md`` already does — open the file
        and point the panel somewhere useful — but prefers a project the writer
        has actually opened over the file's bare parent directory.
        """
        try:
            target = path.expanduser().resolve()
        except OSError:
            return path.parent
        best: Path | None = None
        for entry in self.prefs.recent_projects:
            candidate = Path(entry)
            if candidate == target or candidate in target.parents:
                if best is None or len(candidate.parts) > len(best.parts):
                    best = candidate
        return best if best is not None else target.parent

    def _open_doc(self, path: Path, *, must_exist: bool = False) -> bool:
        """Open ``path`` in a tab. The single open path for every caller.

        ``must_exist`` guards opens sourced from a remembered list: a file that
        has since moved should say so and drop out of the list, not silently
        become an empty buffer bound to a dead path. Typed paths keep the
        opposite behavior on purpose — naming a file that isn't there yet is how
        you create one.
        """
        if must_exist and not path.is_file():
            self.notify(f"{path.name} is no longer there", severity="warning")
            self.prefs.recent_files = [
                x for x in self.prefs.recent_files if Path(x) != path
            ]
            self.prefs.save()
            return False
        self._sync_document_from_editor()
        # Opening bypasses _switch_tab, so note the caret here too — otherwise
        # the tab we're leaving forgets where you were.
        self._remember_caret()
        try:
            self.workspace.open_path(path)
        except OSError as exc:
            self.notify(f"Open failed: {exc}", severity="error")
            return False
        self._find.reset()
        self._load_active_into_editor()
        self._refresh_status()
        self._restore_caret()
        try:
            self.query_one("#editor", TextArea).focus()
        except Exception:
            pass
        if path.exists():
            self._record_recent_file(path)
            self.notify(f"Opened {path.name}")
        else:
            self.notify(f"New buffer for {path} (not on disk yet)")
        self._reveal_active_file()
        self.run_worker(self._maybe_restore(path))
        return True

    def _capture_session(self) -> None:
        """Record the open tabs so the splash can offer them back.

        Only titled buffers survive: an untitled one has nothing to reopen from.
        The caret of the active tab comes from the editor, the rest from what
        was stored when they were last active.
        """
        if not self.prefs.restore_session:
            return
        editor = self._editor_or_none()
        if editor is not None:
            row, col = editor.cursor_location
            active_doc = self.workspace.active
            if active_doc.path is not None:
                self._caret_memory[str(active_doc.path)] = (row, col)

        files: list[OpenFile] = []
        active = 0
        for doc in self.workspace.documents:
            if doc.path is None:
                continue
            if doc is self.workspace.active:
                active = len(files)
            row, col = self._caret_memory.get(str(doc.path), (0, 0))
            files.append(OpenFile(doc.path, row, col))
        root = self._path_arg if self._path_arg is not None else None
        session_save(session_path(), Session(files=files, active=active, project_root=root))

    def _restore_session(self, session: Session) -> None:
        """Reopen a saved session's tabs and put each caret back."""
        session = session.existing()
        if session.is_empty:
            self.notify("Those files are no longer there", severity="warning")
            return
        if session.project_root is not None and session.project_root.is_dir():
            self._set_project_root(session.project_root, focus_tree=False)
        for f in session.files:
            self._caret_memory[str(f.path)] = (f.line, f.column)
            self._open_doc(f.path, must_exist=True)
        if session.active < self.workspace.count:
            self.workspace.set_active(session.active)
            self._load_active_into_editor()
            self._refresh_status()
        self._restore_caret()
        self.notify(f"Reopened {self.workspace.count} file(s)")

    def _restore_caret(self) -> None:
        """Put the caret back where it was for the active document."""
        doc = self.workspace.active
        editor = self._editor_or_none()
        if doc.path is None or editor is None:
            return
        remembered = self._caret_memory.get(str(doc.path))
        if remembered is None:
            return
        row, col = remembered
        try:
            row = min(row, editor.document.line_count - 1)
            col = min(col, len(editor.document.get_line(row)))
            editor.move_cursor((row, col))
            editor.scroll_cursor_visible()
        except Exception:
            pass

    def _save_base_dir(self) -> Path:
        """Where a typed relative path lands: project root → file's folder → cwd."""
        if self._path_arg is not None:
            return self._project_root()
        doc_path = self.workspace.active.path
        if doc_path is not None:
            return doc_path.parent
        return Path.cwd()

    def _untitled_default(self) -> Path:
        """Default path offered when saving a buffer that has never had one."""
        return self._save_base_dir() / f"untitled{_DEFAULT_SUFFIX}"

    def _set_project_root(self, root: Path, *, focus_tree: bool = True) -> None:
        """Point the panel at ``root``, open it, and record it as recent."""
        try:
            panel = self.query_one("#project-panel", ProjectPanel)
        except Exception:
            return
        self._path_arg = root
        panel.set_root(root)
        panel.open()
        self._update_prose_layout()  # prose re-centers clear of the panel
        if focus_tree:
            panel.focus_tree()
        self._record_recent_project(root)
        self.notify(f"Project: {root.name or root}")

    def _build_commands(self) -> None:
        r = self.registry

        def add(
            id: str,
            label: str,
            menu: str,
            handler,
            binding: str | None = None,
            enabled=None,
            checked=None,
        ) -> None:
            r.register(
                Command(
                    id=id,
                    label=label,
                    menu=menu,
                    binding=binding,
                    handler=handler,
                    enabled=enabled,
                    checked=checked,
                )
            )

        # File — all single-key or menu-only. Save As / Save All are menu-only
        # (no portable single key worth spending; they're infrequent).
        add("new_file", "New File", "File", self.cmd_new_file, "ctrl+n")
        add("open_file", "Open File…", "File", self.cmd_open_file, "ctrl+o")
        add("open_folder", "Open Folder…", "File", self.cmd_open_folder)  # menu
        add("recent_projects", "Recent Projects…", "File", self.cmd_welcome)  # menu
        add("close", "Close", "File", self.cmd_close, "ctrl+w")
        add("close_others", "Close Others", "File", self.cmd_close_others)  # menu only
        add("close_all", "Close All", "File", self.cmd_close_all)  # menu only
        add("save", "Save", "File", self.cmd_save, "ctrl+s")
        add("save_as", "Save As…", "File", self.cmd_save_as)  # menu only
        add("save_all", "Save All", "File", self.cmd_save_all)  # menu only
        add("export", "Export…", "File", self.cmd_export, "f5")
        add("find_in_project", "Find in Project…", "File", self.cmd_find_in_project)
        add("compile", "Compile…", "File", self.cmd_compile)  # expand includes → .md
        add("quit", "Exit", "File", self.cmd_quit, "ctrl+q")

        # Edit
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
            "ctrl+y",  # single key (Ctrl+Shift+Z is not portable)
            enabled=lambda: self.document.can_redo,
        )
        add("find", "Find…", "Edit", self.cmd_find, "ctrl+f")
        add("replace", "Replace…", "Edit", self.cmd_replace, "ctrl+r")
        # F3 is the near-universal "next match" key, and it works from the text:
        # stepping through hits used to require keeping the find bar focused.
        add("find_next", "Find Next", "Edit", self.cmd_find_next, "f3")
        add("find_prev", "Find Previous", "Edit", self.cmd_find_prev)  # ↑ in find bar
        add("replace_one", "Replace", "Edit", self.cmd_replace_one)  # Enter in replace field
        add("replace_all", "Replace All", "Edit", self.cmd_replace_all)  # menu + bar buttons
        add("select_all", "Select All", "Edit", self.cmd_select_all, "ctrl+a")
        add("duplicate_line", "Duplicate Line", "Edit", self.action_duplicate_line)  # menu
        add("move_line_up", "Move Line Up", "Edit", self.action_move_line_up)  # menu
        add("move_line_down", "Move Line Down", "Edit", self.action_move_line_down)  # menu

        # Format — inserts/wraps Markdown. Bold + Italic get single keys
        # (Ctrl+I is impossible — it's Tab — so italic is Ctrl+E "emphasis").
        add("fmt_bold", "Bold", "Format", self.cmd_bold, "ctrl+b")
        add("fmt_italic", "Italic", "Format", self.cmd_italic, "ctrl+e")
        add("fmt_strike", "Strikethrough", "Format", self.cmd_strikethrough)
        add("fmt_code", "Inline Code", "Format", self.cmd_inline_code)
        add("fmt_link", "Link", "Format", self.cmd_link)
        add("fmt_heading", "Heading", "Format", self.cmd_heading)
        add("fmt_quote", "Blockquote", "Format", self.cmd_blockquote)
        add("fmt_bullet", "Bullet List", "Format", self.cmd_bullet_list)
        add("fmt_number", "Numbered List", "Format", self.cmd_numbered_list)
        add("fmt_rule", "Horizontal Rule", "Format", self.cmd_hrule)
        add("fmt_fence", "Code Fence", "Format", self.cmd_code_fence)
        add("fmt_include", "Include File", "Format", self.cmd_include)

        # View
        add(
            "toggle_project",
            "Project Panel",
            "View",
            self.cmd_toggle_project_panel,
            "ctrl+p",
        )
        # Advertise the key that actually arrives everywhere; Ctrl+PageUp/Down
        # still work (see BINDINGS) but must not be what the menu promises.
        add("next_tab", "Next Tab", "View", self.cmd_next_tab, "f6")
        add("prev_tab", "Previous Tab", "View", self.cmd_prev_tab, "shift+f6")
        add("outline", "Outline…", "View", self.cmd_outline, "f4")
        add("toggle_soft_wrap", "Soft Wrap", "View", self.cmd_toggle_soft_wrap)  # menu
        add(
            "toggle_line_numbers",
            "Line Numbers",
            "View",
            self.cmd_toggle_line_numbers,
            checked=lambda: self.prefs.line_numbers,
        )
        add("toggle_center", "Center Text", "View", self.cmd_toggle_center)  # menu
        add("toggle_zen", "Zen Mode", "View", self.cmd_toggle_zen)  # menu
        add(
            "toggle_spellcheck",
            "Spellcheck",
            "Tools",
            self.cmd_toggle_spellcheck,
            "f7",
            checked=lambda: self._spell.enabled,
        )
        add("spelling", "Spelling…", "Tools", self.cmd_spelling)
        add("suggest", "Suggest Correction", "Tools", self.cmd_suggest, "ctrl+g")
        add("toggle_autosave", "Autosave", "Tools", self.cmd_toggle_autosave)
        add("toggle_formatting", "Formatting Preview", "View", self.cmd_toggle_formatting)
        add("theme_picker", "Theme…", "View", self.cmd_theme_picker)
        add("cycle_theme", "Next Theme", "View", self.cmd_cycle_theme)
        add("toggle_mouse", "Mouse Capture", "View", self.cmd_toggle_mouse_capture)

        add("toggle_starbot", "StarBot Chat", "Project", self.cmd_toggle_starbot, "ctrl+k")
        add("starbot_new_chat", "New StarBot Chat", "Project", self.cmd_starbot_new_chat)
        add("starbot_history", "StarBot History…", "Project", self.cmd_starbot_history)
        add("starbot_config", "StarBot…", "Project", self.cmd_starbot_config)

        add("welcome", "Welcome…", "Help", self.cmd_welcome)
        add(
            "keyboard_shortcuts",
            "Keyboard Shortcuts…",
            "Help",
            self.cmd_keyboard_shortcuts,
            "f1",
        )
        add("about", "About…", "Help", self.cmd_about)
        add("send_feedback", "Send Feedback…", "Help", self.cmd_send_feedback)

    def compose(self) -> ComposeResult:
        # First terminal line when open (dock top) — not a modal overlay.
        yield MenuBar(self.registry, id="app-menu")
        with Vertical(id="main"):
            # blank · filename · blank · thin rule · (find) · editor
            with Vertical(id="tab-strip"):
                yield Static("", id="tab-pad-top")
                yield TabBar("", id="tab-label")  # chips built in _refresh_status
                # No blank row under the tab label — rule sits tight underneath
                yield Static("", id="tab-rule")
            yield FindBar(id="find-bar")
            yield SpellBar(id="spell-bar")
            with Horizontal(id="editor-row"):
                yield ProjectPanel(self._project_root(), id="project-panel")
                yield Static("", id="editor-left-pad")
                yield MarkStarTextArea(id="editor")
                yield Static("", id="editor-right-pad")
                yield StarBotPanel(id="starbot-panel")
            with Vertical(id="bottom-chrome"):
                with Horizontal(id="status-rule-row"):
                    yield Static("", id="status-rule")
                yield Static("", id="support-pad-top")
                with Horizontal(id="support-row"):
                    yield Static("", id="support-hints")
                    yield Static("", id="support-metrics")
                yield Static("", id="support-pad-bottom")

    # Support-strip shortcuts (key label shown in blue, description dim).
    # The menu holds the full command list; the footer stays quiet.
    _SUPPORT_HINTS: list[tuple[str, str]] = [
        ("Esc", "Menu"),
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

        editor = self.query_one("#editor", MarkStarTextArea)
        # Apply saved preferences.
        editor.soft_wrap = self.prefs.soft_wrap
        editor.render_markdown = self.prefs.formatting
        editor.prose_width = self.prefs.prose_width
        editor.show_line_numbers = self.prefs.line_numbers
        # No distinct "paper" band or gutter chrome
        editor.highlight_cursor_line = False
        self._apply_editor_theme()
        self._sync_terminal_bg()

        launch_root: Path | None = None  # folder to open the panel at
        launch_focus_tree = False
        launch_file: Path | None = None  # file to check for a restore sidecar
        if self._path_arg is not None:
            try:
                is_dir = self._path_arg.is_dir()
            except OSError:
                is_dir = False
            if is_dir:
                # `markstar <folder>` → project root = that folder; browse it.
                launch_root = self._path_arg
                launch_focus_tree = True
            elif self._path_arg.exists():
                # `markstar <folder>/file.md` → open the file AND show its folder
                # tree; focus stays in the editor.
                self.workspace.open_path(self._path_arg)
                launch_root = self._path_arg.parent
                launch_file = self._path_arg
            else:
                self.workspace.active.path = self._path_arg
        self._load_active_into_editor()
        editor.focus()
        self._refresh_status()
        self._update_prose_layout()

        if launch_root is not None:
            self._set_project_root(launch_root, focus_tree=launch_focus_tree)
        elif self._path_arg is None and not self.is_headless:
            # Fresh launch (no arg) → welcome screen. Skipped under headless tests.
            self.call_after_refresh(lambda: self.run_worker(self._show_welcome()))

        if launch_file is not None:
            self.run_worker(self._maybe_restore(launch_file))

        if self._spell.enabled:
            self.call_after_refresh(self._spell.run)

    def on_resize(self, event) -> None:
        # Use the size the event carries, not self.size — the latter isn't updated
        # until after this handler runs, so reading it here lags one resize behind
        # (rules/padding keep the *previous* window's width). See event.size.
        width = None
        try:
            width = event.size.width
        except Exception:
            width = None
        self._update_prose_layout(width)

    def on_unmount(self) -> None:
        self._reset_terminal_bg()

    def _apply_editor_theme(self) -> None:
        """Give the editor a TextArea theme whose background/foreground match the
        active app theme exactly (Textual's built-in vscode_dark paints #1f1f1f,
        a hair lighter than our $background — that mismatch is visible).

        The editor theme is named per app-theme (``ms-editor-<theme>``) so that
        setting ``editor.theme`` on a switch is always a real change — a fixed
        name would no-op and leave a stale background (visible when previewing
        themes in the picker)."""
        import dataclasses

        try:
            from textual.widgets.text_area import TextAreaTheme

            editor = self.query_one("#editor", MarkStarTextArea)
            base = TextAreaTheme.get_builtin_theme("vscode_dark")
            if base is None:
                return
            # Read straight from the Theme object: self.theme_variables lags one
            # step behind self.theme (it updates on a later refresh), which would
            # give the editor the *previous* theme's background.
            theme_obj = self.get_theme(self.theme)
            if theme_obj is None:
                return  # no hardcoded fallback — every color comes from the theme
            bg = theme_obj.background
            fg = theme_obj.foreground
            sel = theme_obj.variables.get("search-match", theme_obj.primary)
            ed_name = f"ms-editor-{self.theme}"
            themed = dataclasses.replace(
                base,
                name=ed_name,
                base_style=Style(color=fg, bgcolor=bg),
                selection_style=Style(bgcolor=sel),
                cursor_line_style=Style(bgcolor=bg),
                # Line numbers, when shown, sit clearly below the prose: they
                # are a reference, not part of what you are reading.
                gutter_style=Style(color=token(self, "rule"), bgcolor=bg),
                cursor_line_gutter_style=Style(color=token(self, "hint-key"), bgcolor=bg),
            )
            try:
                editor.register_theme(themed)
            except Exception:
                pass  # already registered under this name
            editor.theme = ed_name
        except Exception:
            pass

    def _compute_layout(self, width: int, panel_open: bool) -> ProseLayout:
        """Prose column geometry for ``width`` — pure math in ui/layout.py, fed
        the relevant preferences."""
        return compute_layout(
            width,
            panel_open,
            center_text=self.prefs.center_text,
            prose_width=self.prefs.prose_width,
            min_panel_width=self.prefs.min_panel_width,
        )

    def _panel_open(self) -> bool:
        try:
            return self.query_one("#project-panel", ProjectPanel).is_open
        except Exception:
            return False

    def _update_prose_layout(self, width: int | None = None) -> None:
        """Position tabs, rules, editor, footer and menu into one centered prose
        column that sits clear of the project panel. Recomputed on every resize
        and whenever the panel opens/closes.

        ``width`` may be passed explicitly (e.g. from a Resize event, whose size
        is fresh) — otherwise the current ``self.size`` is used."""
        if width is None:
            width = self.size.width or 0
        panel, left_pad, col, right_pad = self._compute_layout(width, self._panel_open())

        if panel:
            try:
                self.query_one("#project-panel", ProjectPanel).styles.width = panel
            except Exception:
                pass
        # StarBot mirrors the project panel's width (fills its margin the same way),
        # independent of whether the project panel itself is open.
        if self._starbot_open():
            sb_w = max(self.prefs.min_panel_width, left_pad - PANEL_GAP)
            try:
                self.query_one("#starbot-panel", StarBotPanel).styles.width = min(
                    sb_w, width
                )
            except Exception:
                pass
        # Line numbers live in the left margin, not in the writing measure:
        # switching them on must not slide the prose sideways under the reader.
        # Steal their width back from the pad so the text stays put.
        try:
            editor = self.query_one("#editor", MarkStarTextArea)
            if editor.show_line_numbers:
                left_pad = max(0, left_pad - editor.gutter_width)
        except Exception:
            pass
        try:
            self.query_one("#editor-left-pad").styles.width = left_pad
        except Exception:
            pass
        try:
            self.query_one("#editor-right-pad").styles.width = right_pad
        except Exception:
            pass
        # Tabs + rules align with the editor column.
        for sel in ("#tab-strip", "#status-rule-row"):
            try:
                self.query_one(sel).styles.padding = (0, right_pad, 0, left_pad)
            except Exception:
                pass
        # Footer content sits 3 cols inside the prose column on BOTH sides (the
        # left matches the tab chip's leading spaces; the right mirrors it so the
        # metrics corner is inset the same as the hints corner).
        try:
            self.query_one("#support-row").styles.padding = (
                0,
                right_pad + 3,
                0,
                left_pad + 3,
            )
        except Exception:
            pass
        # Menu ribbon + dropdown align with the tabs.
        try:
            self.query_one("#app-menu #menu-names", Static).styles.padding = (0, 0, 0, left_pad)
        except Exception:
            pass
        try:
            self.query_one("#app-menu #menu-options").styles.margin = (0, 0, 0, left_pad)
        except Exception:
            pass
        self._refresh_metrics()
        self._set_prose_rules(col)

    def _set_prose_rules(self, col: int) -> None:
        """Fill the top/bottom rules to exactly the prose-column width.

        Uses ``col`` from _compute_layout directly (the content width between the
        paddings) rather than reading the rules' laid-out size — the latter lags a
        frame behind on resize, so reading it left a stub rule when *growing* the
        window (and required a retry loop when shrinking). Deterministic now."""
        line = "─" * max(1, col)
        for rule_id in ("#status-rule", "#tab-rule"):
            try:
                rule = self.query_one(rule_id, Static)
            except Exception:
                continue
            if not rule.display:  # e.g. hidden in zen mode
                continue
            rule.update(line)

    @on(TextArea.Changed)
    def _on_editor_changed(self, event: TextArea.Changed) -> None:
        # flush() pulls the edit into the active Document (and reports whether it
        # actually changed). Don't read self.document above this — it would flush
        # first and make the "did anything change?" check always false.
        if not self._session.flush():
            return
        self._refresh_status()
        # Fenced code blocks are multi-line — recompute which lines are in a fence.
        if isinstance(event.text_area, MarkStarTextArea):
            event.text_area.recompute_fences()
        self._schedule_spellcheck()
        self._schedule_autosave()
        # Keep soft find highlights in sync while typing in the buffer.
        try:
            if self.query_one("#find-bar", FindBar).is_visible:
                self._find.refresh_highlights()
        except Exception:
            pass

    @on(TextArea.SelectionChanged)
    def _on_selection_changed(self, event: TextArea.SelectionChanged) -> None:
        self._refresh_metrics()

    def _sync_document_from_editor(self) -> None:
        self._session.flush()

    def _push_document_to_editor(self) -> None:
        self._load_active_into_editor()
        self._refresh_metrics()

    def _load_active_into_editor(self) -> None:
        self._session.load_active()

    def _switch_tab(self, switcher) -> None:
        """Sync editor → doc, switch tab via callable, load new doc."""
        self._sync_document_from_editor()
        self._remember_caret()
        switcher()
        self._find.reset()
        self._load_active_into_editor()
        self._refresh_status()
        self._restore_caret()
        self._reveal_active_file()

    def _remember_caret(self) -> None:
        """Note where the caret sits in the tab we're leaving."""
        doc = self.workspace.active
        editor = self._editor_or_none()
        if doc.path is not None and editor is not None:
            self._caret_memory[str(doc.path)] = editor.cursor_location

    def _reveal_active_file(self) -> None:
        """Point the project tree at whatever file is now in the editor.

        Fire-and-forget: revealing is a courtesy, and a file outside the project
        (or a tree still loading) simply doesn't get one.
        """
        path = self.workspace.active.path
        if path is None:
            return
        try:
            panel = self.query_one("#project-panel", ProjectPanel)
        except Exception:
            return
        if not panel.is_open:
            return
        self.run_worker(panel.reveal(path), exclusive=True, group="reveal")

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
        """Themed keys + dim labels (labels/pipes inherit $text-muted from CSS)."""
        hk = token(self, "hint-key")
        parts: list[str] = []
        for key, desc in self._SUPPORT_HINTS:
            # Only the key is colored (theme token); description uses widget muted.
            parts.append(f"[{hk}]{key}[/] {desc}")
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
        """Paint the footer stats, recounting in the background when stale.

        Counting prose means stripping the markup out of the whole buffer, which
        on a book-length document costs tens of milliseconds — far too much to
        pay on the keystroke path, and this is reached from every cursor move
        and every edit. So the footer always paints from the last known counts
        and schedules a recount, exactly as spellcheck debounces its pass. The
        numbers lag typing by a fraction of a second; nobody watches a word
        count mid-sentence, and the editor stays responsive.
        """
        editor = self._editor_or_none()
        selection = editor.selection if editor is not None else None
        if self.document.text is not self._counts_text or selection != self._sel_range:
            self._schedule_recount()
        self._paint_metrics()

    def _editor_or_none(self):
        try:
            return self.query_one("#editor", TextArea)
        except Exception:
            return None

    def _schedule_recount(self) -> None:
        if self._counts_timer is not None:
            try:
                self._counts_timer.stop()
            except Exception:
                pass
        self._counts_timer = self.set_timer(_METRICS_DEBOUNCE, self._recount)

    def _recount(self) -> None:
        """Recompute prose counts for the document and any selection."""
        self._counts_timer = None
        text = self.document.text
        self._counts_text = text
        self._counts = wordcount.count(text)

        editor = self._editor_or_none()
        self._sel_range = editor.selection if editor is not None else None
        selected = ""
        if editor is not None and not editor.selection.is_empty:
            selected = editor.selected_text
        self._sel_words = wordcount.count(selected).words if selected else 0
        self._paint_metrics()

    def _paint_metrics(self) -> None:
        """Right-aligned stats, shortened on narrow terminals so they don't
        overflow the footer."""
        words, chars = self._counts.words, self._counts.characters
        picked = self._sel_words
        width = self.size.width or 0
        if width < _METRICS_NARROW:
            text = f"{picked}/{words}w" if picked else f"{words}w"
        elif width < _METRICS_MEDIUM:
            text = f"{chars}c  │  " + (f"{picked}/{words}w" if picked else f"{words}w")
        else:
            text = f"{chars:,} characters  │  {words:,} words"
            if picked:
                text += f"  │  {picked:,} selected"
            text += "  │  CommonMark"
        try:
            self.query_one("#support-metrics", Static).update(text)
        except Exception:
            pass

    def _refresh_status(self) -> None:
        """Tab ribbon (all open docs, clickable), metrics, and terminal title.

        Chip: ``   {name} {•} × │`` — name/dirty in the tab color, the close ×
        and the │ separator both in the dim rule color. Click bounds recorded
        in ``self._tab_bounds`` = (start, end, close_col, index).
        """
        tabs = [
            TabInfo(doc.path.name if doc.path else "Untitled", doc.dirty)
            for doc in self.workspace.documents
        ]
        try:
            self.query_one("#tab-label", TabBar).set_tabs(
                tabs, self.workspace.active_index
            )
        except Exception:
            pass

        self._refresh_metrics()
        _, _, col, _ = self._compute_layout(self.size.width or 0, self._panel_open())
        self._set_prose_rules(col)
        self._refresh_panel_open_files()
        name = self.document.path.name if self.document.path else "Untitled"
        self.title = f"{name}{' •' if self.document.dirty else ''}"

    def _refresh_panel_open_files(self) -> None:
        """Tell the project panel which files are open (bright) and active."""
        open_paths: set[str] = set()
        active: str | None = None
        for i, doc in enumerate(self.workspace.documents):
            if doc.path is None:
                continue
            try:
                key = str(doc.path.resolve())
            except Exception:
                continue
            open_paths.add(key)
            if i == self.workspace.active_index:
                active = key
        try:
            self.query_one("#project-panel", ProjectPanel).set_open_files(
                open_paths, active
            )
        except Exception:
            pass

    @on(TabBar.Activated)
    def _on_tab_activated(self, event: TabBar.Activated) -> None:
        if event.index != self.workspace.active_index:
            self._switch_tab(lambda i=event.index: self.workspace.set_active(i))

    @on(TabBar.Closed)
    def _on_tab_closed(self, event: TabBar.Closed) -> None:
        self._sync_document_from_editor()
        if event.index != self.workspace.active_index:
            self.workspace.set_active(event.index)
        self.cmd_close()

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
        # A screen's own close beats Textual's inherited ``action_dismiss``,
        # which is generic *and* a coroutine — calling that one without
        # awaiting it just leaks a coroutine and leaves the screen open.
        if len(self.screen_stack) > 1:
            screen = self.screen
            for name in ("action_cancel", "action_close", "action_dismiss"):
                action = getattr(screen, name, None)
                if callable(action):
                    result = action()
                    if inspect.isawaitable(result):
                        self.run_worker(result)
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
            spell = self.query_one("#spell-bar", SpellBar)
            if spell.is_visible:
                spell.hide()
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

        # Project panel: close it (and return focus to the editor) before Esc
        # falls through to summoning the menu.
        try:
            panel = self.query_one("#project-panel", ProjectPanel)
            if panel.is_open:
                panel.close()
                self._update_prose_layout()
                self.query_one("#editor", TextArea).focus()
                return
        except Exception:
            pass

        self._toggle_menu(None)

    def on_key(self, event: Key) -> None:
        """Hard fallback: some terminals drop priority bindings while TextArea is focused.

        Only the small, portable keymap is handled here (all single-stroke). No
        Ctrl+Shift, no chords — see docs/MARKSTAR_KEYMAP.md.
        """
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
        if key == "f9":
            event.stop()
            self._toggle_menu(None)
            return
        if key == "ctrl+pagedown":
            event.stop()
            self.cmd_next_tab()
            return
        if key == "ctrl+pageup":
            event.stop()
            self.cmd_prev_tab()
            return
        if key == "ctrl+p":
            event.stop()
            self.cmd_toggle_project_panel()
            return
        if key == "ctrl+g":
            event.stop()
            self.cmd_suggest()
            return
        if key == "f7":
            event.stop()
            self.cmd_toggle_spellcheck()
            return
        if key == "ctrl+b":
            event.stop()
            self.cmd_bold()
            return
        if key == "ctrl+e":
            event.stop()
            self.cmd_italic()
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
        # When the project tree has focus, create a named file at the selected
        # folder location instead of a blank untitled buffer.
        if isinstance(self.focused, WriterTree):
            self.run_worker(self._new_file_in_tree())
            return
        self._sync_document_from_editor()
        self.workspace.new_document()
        self._find.reset()
        self._load_active_into_editor()
        self._refresh_status()
        self.notify("New file")

    async def _new_file_in_tree(self) -> None:
        """Prompt for a name (prefilled with the selected folder), create the
        empty file on disk, open it, and refresh the tree. Never overwrites."""
        try:
            panel = self.query_one("#project-panel", ProjectPanel)
        except Exception:
            return
        folder = panel.target_dir()
        raw = await self.push_screen_wait(
            PathPrompt(
                "New file — name it",
                initial=str(folder) + "/",
                hint="Enter create · Esc cancel · bare name → .md",
            )
        )
        if raw is None:
            return
        path = self._normalize_save_path(raw)
        if path is None:
            self.notify("Empty name — nothing created", severity="warning")
            return
        existed = path.exists()
        if existed:
            if path.is_dir():
                self.notify(
                    f"{path.name} is a folder — pick a file name", severity="warning"
                )
                return
            # Never overwrite: open the existing file instead.
            self.notify(f"{path.name} already exists — opening it", severity="warning")
        else:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            except OSError as exc:
                self.notify(f"Create failed: {exc}", severity="error")
                return
        if not self._open_doc(path):
            return
        panel.refresh_tree()
        if not existed:
            self.notify(f"Created {path.name}")

    def cmd_open_file(self) -> None:
        """Quick Open — fuzzy-match recents and the project tree (Ctrl+O)."""
        self.run_worker(self._quick_open_async())

    def action_open_file(self) -> None:
        self.cmd_open_file()

    async def _quick_open_async(self) -> None:
        recents = self._recent_files()
        root = self._project_root() if self._path_arg is not None else None
        picked = await self.push_screen_wait(QuickOpenScreen(recents, root))
        if picked is None:
            return
        # A row the writer picked from the list must still be there; a path they
        # typed themselves may legitimately not be.
        from_list = str(picked) in recents or (
            root is not None and picked.is_relative_to(root) and picked.exists()
        )
        self._open_doc(picked, must_exist=from_list)

    def cmd_toggle_project_panel(self) -> None:
        """Ctrl+P — reach the panel, then leave it. Three states, one key.

        Closed → open it and put the cursor in the tree. Open but you're typing
        → jump focus to the tree (this used to close the very panel you were
        reaching for). Open and already focused → close and go back to writing.
        """
        try:
            panel = self.query_one("#project-panel", ProjectPanel)
        except Exception:
            return
        if not panel.is_open:
            panel.open()
            panel.refresh_tree()  # catch anything added since it was last shown
            panel.focus_tree()
            self._reveal_active_file()
        elif not panel.has_focus_within:
            # Taking focus is the natural moment to notice files that appeared
            # (or vanished) outside MarkStar since you last looked.
            panel.refresh_tree()
            panel.focus_tree()
            self._reveal_active_file()
        else:
            panel.close()
            self.query_one("#editor", TextArea).focus()
        self._update_prose_layout()  # prose re-centers clear of the panel

    def action_toggle_project(self) -> None:
        self.cmd_toggle_project_panel()

    def cmd_welcome(self) -> None:
        """Re-open the welcome screen (Help > Welcome)."""
        self.run_worker(self._show_welcome())

    async def _show_welcome(self) -> None:
        recent = [Path(p) for p in self.prefs.recent_projects]
        files: list[tuple[Path, float]] = []
        for entry in self._recent_files():
            p = Path(entry)
            try:
                files.append((p, p.stat().st_mtime))
            except OSError:
                continue
        saved = session_load(session_path()).existing() if self.prefs.restore_session else Session()
        choice = await self.push_screen_wait(
            WelcomeScreen(
                self._project_root(), __version__, recent, files, len(saved.files)
            )
        )
        if choice is None or choice.kind == "new":
            return  # blank buffer, already waiting behind the modal
        if choice.kind == "session":
            self._restore_session(saved)
            return
        if choice.kind == "quick_open":
            await self._quick_open_async()
            return
        if choice.kind == "file" and choice.path is not None:
            # Point the panel at the file's project so the tree is useful, the
            # same way `markstar <folder>/file.md` already behaves.
            self._set_project_root(
                self._infer_project_root(choice.path), focus_tree=False
            )
            self._open_doc(choice.path, must_exist=True)
            return

        root = choice.path
        if root is None:
            return
        if root.is_dir():
            self._set_project_root(root)
        elif root.exists():
            self.notify(f'"{root.name}" is a file, not a folder', severity="warning")
        else:
            ok = await self.push_screen_wait(
                ConfirmDialog(
                    title="Create new project?",
                    message=f'No folder at "{root}".\n'
                    "Create it as a new project folder?",
                    yes_label="create",
                    no_label="cancel",
                )
            )
            if ok:
                try:
                    root.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    self.notify(f"Could not create folder: {exc}", severity="error")
                    return
                self._set_project_root(root)

    def cmd_open_folder(self) -> None:
        """Prompt for a folder and point the project panel at it (opens it)."""
        self.run_worker(self._open_folder_async())

    async def _open_folder_async(self) -> None:
        raw = await self.push_screen_wait(
            PathPrompt(
                "Open Folder — enter a directory path",
                initial=str(self._project_root()) + "/",
                hint="Enter open · Esc cancel · ~ allowed",
            )
        )
        if raw is None:
            return
        text = raw.strip().strip('"').strip("'")
        if not text:
            return
        path = Path(text).expanduser()
        if not path.is_dir():
            self.notify(f"Not a folder: {path}", severity="warning")
            return
        self._set_project_root(path)

    @on(WriterTree.FileSelected)
    def _on_tree_file_selected(self, event: WriterTree.FileSelected) -> None:
        """Open the chosen file in a tab (keep the panel open for browsing).

        Only Markdown/plain-text documents are openable; other files (images,
        PDFs, binaries) are link/embed targets and are left in place."""
        event.stop()
        path = Path(event.path)
        if not is_openable(path):
            self.notify(
                f"{path.name} isn't a Markdown document — link to it instead",
                severity="warning",
            )
            return
        self._open_doc(path)

    @staticmethod
    def _doc_name(doc: Document) -> str:
        return doc.path.name if doc.path else "Untitled"

    async def _resolve_dirty(
        self, indices: list[int], *, allow_save_all: bool
    ) -> bool:
        """Ask about each dirty buffer in ``indices``. False = the writer cancelled.

        Decides only — closing is left to the caller, so the workspace's
        "always at least one tab" invariant stays in one place. Each buffer is
        made active before its dialog so the writer is looking at the thing
        they're deciding about.
        """
        save_all = False
        for i in indices:
            if i >= self.workspace.count:
                continue
            doc = self.workspace.documents[i]
            if not doc.dirty:
                continue

            if save_all and doc.path is not None:
                try:
                    doc.save()
                    delete_sidecar(doc.path)
                except OSError as exc:
                    self.notify(
                        f"Save failed ({doc.path.name}): {exc}", severity="error"
                    )
                    return False
                continue

            self.workspace.set_active(i)
            self._load_active_into_editor()
            self._refresh_status()
            answer = await self.push_screen_wait(
                SaveChangesDialog(
                    self._doc_name(doc), show_save_all=allow_save_all
                )
            )
            if answer == "cancel" or answer is None:
                return False
            if answer == "save_all":
                save_all = True
                answer = "save"
            if answer == "discard":
                # Explicitly thrown away — drop the crash sidecar too, or it
                # would offer this work back on the next open.
                if doc.path is not None:
                    delete_sidecar(doc.path)
                continue
            # "save"
            if doc.path is None:
                ok = await self._prompt_and_save_async(
                    title=f'Save "{self._doc_name(doc)}" — where?',
                    initial=str(self._untitled_default()),
                )
            else:
                ok = self._write_active_document()
            if not ok:
                return False  # cancelled or failed → abort the whole operation
        return True

    def cmd_close(self) -> None:
        self.run_worker(self._close_active_async())

    async def _close_active_async(self) -> None:
        self._sync_document_from_editor()
        if self.workspace.active.dirty:
            if not await self._resolve_dirty(
                [self.workspace.active_index], allow_save_all=False
            ):
                return
        self.workspace.close_active()
        self._find.reset()
        self._load_active_into_editor()
        self._refresh_status()

    def cmd_close_others(self) -> None:
        """Close every tab except the active one, asking about each dirty one."""
        self.run_worker(self._close_others_async())

    async def _close_others_async(self) -> None:
        self._sync_document_from_editor()
        if self.workspace.count <= 1:
            self.notify("No other tabs to close")
            return
        keep = self.workspace.active
        others = [
            i
            for i, doc in enumerate(self.workspace.documents)
            if doc is not keep and doc.dirty
        ]
        if others and not await self._resolve_dirty(others, allow_save_all=False):
            return
        # The walk moved the active tab around. Put it back AND reload the
        # editor — _do_close_others syncs the editor into the active document
        # first, so a stale buffer here would overwrite the tab we're keeping.
        for i, doc in enumerate(self.workspace.documents):
            if doc is keep:
                self.workspace.set_active(i)
                self._load_active_into_editor()
                break
        self._do_close_others()

    def action_close_others(self) -> None:
        self.cmd_close_others()

    def _do_close_others(self) -> None:
        self._sync_document_from_editor()
        closed = self.workspace.count - 1
        self.workspace.close_others()
        self._find.reset()
        self._load_active_into_editor()
        self._refresh_status()
        self.notify(f"Closed {closed} other tab(s)")

    def cmd_close_all(self) -> None:
        """Close every tab (leave one empty), asking about each dirty one."""
        self.run_worker(self._close_all_async())

    async def _close_all_async(self) -> None:
        self._sync_document_from_editor()
        dirty = [i for i, doc in enumerate(self.workspace.documents) if doc.dirty]
        if dirty and not await self._resolve_dirty(dirty, allow_save_all=True):
            return
        self._do_close_all()

    def _do_close_all(self) -> None:
        self._sync_document_from_editor()
        n = self.workspace.count
        self.workspace.close_all()
        self._find.reset()
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
                    delete_sidecar(doc.path)
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
                initial=str(self._untitled_default()),
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
        if self.document.path is None:
            self.run_worker(
                self._prompt_and_save_async(
                    title="Save — where should this file go?",
                    initial=str(self._untitled_default()),
                )
            )
            return
        self._write_active_document()

    def cmd_save_as(self) -> None:
        """Save active buffer under a new path (always prompts)."""
        initial = (
            str(self.document.path)
            if self.document.path is not None
            else str(self._untitled_default())
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
            # Explicit save → the sidecar is now stale; remove it.
            if self.document.path is not None:
                delete_sidecar(self.document.path)
                if path is not None:  # named by the writer → worth remembering
                    self._record_recent_file(self.document.path)
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
            PathPrompt(
                title,
                initial=initial or str(self._untitled_default()),
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
                    ConfirmDialog(
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

    def _normalize_save_path(self, raw: str) -> Path | None:
        """Expand typed path text against the right base folder (see savepath)."""
        return resolve_save_path(raw, self._save_base_dir(), _DEFAULT_SUFFIX)

    def action_quit(self) -> None:
        """Override Textual's default action_quit (Ctrl+Q) so we can confirm dirty tabs.

        Textual binds ctrl+q → ``quit`` → ``App.action_quit`` which exits immediately.
        That bypassed ``cmd_quit`` / the command registry.
        """
        self.cmd_quit()

    def cmd_quit(self) -> None:
        self.run_worker(self._quit_async())

    async def _quit_async(self) -> None:
        self._sync_document_from_editor()
        dirty = [i for i, doc in enumerate(self.workspace.documents) if doc.dirty]
        if not dirty:
            self._capture_session()
            self.exit()
            return
        resume = self.workspace.active_index
        self._capture_session()
        if not await self._resolve_dirty(dirty, allow_save_all=True):
            # Cancelled mid-walk: leave the writer where they started.
            if resume < self.workspace.count:
                self.workspace.set_active(resume)
                self._load_active_into_editor()
                self._refresh_status()
            self.notify("Quit cancelled")
            return
        self.exit()

    def cmd_undo(self) -> None:
        if self.document.undo():
            self._push_document_to_editor()
            self._refresh_status()

    def cmd_redo(self) -> None:
        if self.document.redo():
            self._push_document_to_editor()
            self._refresh_status()

    # Find/Replace commands delegate to the FindController (search state + logic).
    def cmd_find(self) -> None:
        """Find in the document — or across the project when the tree has focus.

        Same key, read in context: if you are standing in the file tree, the
        thing you mean to search is the project.
        """
        try:
            panel = self.query_one("#project-panel", ProjectPanel)
            if panel.is_open and panel.has_focus_within:
                self.cmd_find_in_project()
                return
        except Exception:
            pass
        self._find.open(replace=False)

    def cmd_replace(self) -> None:
        self._find.open(replace=True)

    def action_show_replace(self) -> None:
        self.cmd_replace()

    def action_replace_one_key(self) -> None:
        self.cmd_replace_one()

    def action_replace_all_key(self) -> None:
        self.cmd_replace_all()

    def cmd_find_next(self) -> None:
        self._find.find("next")

    def cmd_find_prev(self) -> None:
        self._find.find("prev")

    def action_find_next(self) -> None:
        self.cmd_find_next()

    def action_find_prev(self) -> None:
        self.cmd_find_prev()

    @on(FindBar.CaseToggled)
    def _on_case_toggled(self, event: FindBar.CaseToggled) -> None:
        event.stop()
        on = self._find.toggle_case_sensitive()
        self.query_one("#find-bar", FindBar).set_case_sensitive(on)
        self.notify("Find: match case" if on else "Find: any case")

    @on(FindBar.ExpandReplace)
    def _on_expand_replace(self, event: FindBar.ExpandReplace) -> None:
        self._find.on_expand()

    def cmd_replace_one(self) -> None:
        self._find.replace_one()

    def cmd_replace_all(self) -> None:
        self._find.replace_all()

    def cmd_select_all(self) -> None:
        self.query_one("#editor", TextArea).select_all()

    # --- Format menu: wrap/insert Markdown around the selection ---------------

    def _wrap_selection(self, prefix: str, suffix: str | None = None) -> None:
        """Wrap the current selection in ``prefix``…``suffix`` (suffix=prefix if omitted).

        With no selection, insert both markers and park the caret between them.
        Uses TextArea's own edit API so undo/redo and the document sync work.
        """
        suffix = prefix if suffix is None else suffix
        editor = self.query_one("#editor", TextArea)
        selected = editor.selected_text
        if selected:
            start, end = sorted([editor.selection.start, editor.selection.end])
            editor.replace(f"{prefix}{selected}{suffix}", start, end)
        else:
            editor.insert(f"{prefix}{suffix}")
            row, col = editor.cursor_location
            editor.move_cursor((row, max(0, col - len(suffix))))
        editor.focus()

    def _prefix_current_line(self, marker: str) -> None:
        """Prepend ``marker`` to the caret's line (headings, quotes, list items)."""
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        line = editor.document.get_line(row)
        editor.replace(f"{marker}{line}", (row, 0), (row, len(line)))
        editor.move_cursor((row, col + len(marker)))
        editor.focus()

    def _toggle_emphasis(self, marker: str, regex: "re.Pattern") -> None:
        """Toggle ``marker`` (**, *, ~~, `) on the selection or the word under
        the caret. Thin adapter: reads the editor state, delegates the text/caret
        math to the pure ``markdown.toggle_emphasis``, applies the result."""
        editor = self.query_one("#editor", TextArea)
        (sr, sc), (er, ec) = editor.selection.start, editor.selection.end
        if sr != er:  # multi-line selection → plain wrap (no toggle)
            self._wrap_selection(marker)
            return
        row = sr
        line = editor.document.get_line(row)
        caret = editor.cursor_location[1]
        a, b = sorted((sc, ec)) if sc != ec else word_bounds(line, caret)
        new_line, nc = toggle_emphasis(line, marker, regex, a, b, caret)
        editor.replace(new_line, (row, 0), (row, len(line)))
        editor.move_cursor((row, nc))
        editor.focus()

    def cmd_bold(self) -> None:
        self._toggle_emphasis("**", RE_BOLD)

    def cmd_italic(self) -> None:
        self._toggle_emphasis("*", RE_ITALIC)

    def cmd_strikethrough(self) -> None:
        self._toggle_emphasis("~~", RE_STRIKE)

    def cmd_inline_code(self) -> None:
        self._toggle_emphasis("`", RE_CODE)

    def cmd_link(self) -> None:
        editor = self.query_one("#editor", TextArea)
        selected = editor.selected_text
        if selected:
            start, end = sorted([editor.selection.start, editor.selection.end])
            editor.replace(f"[{selected}](url)", start, end)
        else:
            editor.insert("[text](url)")
        editor.focus()

    def cmd_heading(self) -> None:
        self._prefix_current_line("# ")

    def cmd_blockquote(self) -> None:
        self._prefix_current_line("> ")

    def cmd_bullet_list(self) -> None:
        self._prefix_current_line("- ")

    def cmd_numbered_list(self) -> None:
        self._prefix_current_line("1. ")

    def cmd_hrule(self) -> None:
        editor = self.query_one("#editor", TextArea)
        editor.insert("\n---\n")
        editor.focus()

    def cmd_code_fence(self) -> None:
        self._wrap_selection("```\n", "\n```")

    def cmd_include(self) -> None:
        """Insert an include token ``![[]]`` with the caret between the brackets."""
        editor = self.query_one("#editor", TextArea)
        selected = editor.selected_text
        if selected:
            start, end = sorted([editor.selection.start, editor.selection.end])
            editor.replace(f"![[{selected}]]", start, end)
        else:
            editor.insert("![[]]")
            row, col = editor.cursor_location
            editor.move_cursor((row, max(0, col - 2)))
        editor.focus()

    def _goto_line(self, line: int, column: int = 0) -> None:
        """Put the caret on a 0-based line and show it."""
        editor = self._editor_or_none()
        if editor is None:
            return
        try:
            line = max(0, min(line, editor.document.line_count - 1))
            column = max(0, min(column, len(editor.document.get_line(line))))
            editor.move_cursor((line, column))
            editor.scroll_cursor_visible(center=True)
            editor.focus()
        except Exception:
            pass

    def cmd_outline(self) -> None:
        """Jump to a heading in the active document (F4)."""
        self.run_worker(self._outline_async())

    async def _outline_async(self) -> None:
        found = md_headings(self.document.text)
        if not found:
            self.notify("No headings in this document", severity="warning")
            return
        editor = self._editor_or_none()
        current = editor.cursor_location[0] if editor is not None else 0
        line = await self.push_screen_wait(OutlineScreen(found, current))
        if line is not None:
            self._goto_line(line)

    def cmd_find_in_project(self) -> None:
        """Search every document in the project (Ctrl+F with the tree focused)."""
        self.run_worker(self._find_in_project_async())

    async def _find_in_project_async(self) -> None:
        if self._path_arg is None:
            self.notify("Open a project folder first", severity="warning")
            return
        root = self._project_root()
        raw = await self.push_screen_wait(
            PathPrompt(
                f"Find in {root.name or root}",
                initial="",
                hint="Enter search · Esc cancel",
            )
        )
        if raw is None or not raw.strip():
            return
        query = raw.strip()
        self.notify(f"Searching {root.name or root}…")
        results = await asyncio.get_running_loop().run_in_executor(
            None,
            partial(
                search_project, root, query, case_sensitive=self._find.case_sensitive
            ),
        )
        if not results.hits:
            self.notify(
                f"No hits for {query!r} in {results.files_searched} file(s)",
                severity="warning",
            )
            return
        hit = await self.push_screen_wait(FindResultsScreen(query, results))
        if hit is None:
            return
        if self._open_doc(hit.path, must_exist=True):
            self._goto_line(hit.line, hit.column)

    def cmd_export(self) -> None:
        """Export the manuscript to HTML / DOCX / PDF / EPUB (F5)."""
        self.run_worker(self._export_async())

    def _compiled_text(self) -> str:
        """The active buffer with ``![[includes]]`` expanded — one whole book.

        Exporting the raw buffer would ship a document full of unresolved
        include tokens, so export always goes through the same expansion
        Compile uses.
        """
        doc = self.document
        base_dir = doc.path.parent if doc.path else Path.cwd()
        output, _errors = compile_document(
            doc.text, base_dir, make_resolver(self._project_root()), self_path=doc.path
        )
        return output

    async def _export_async(self) -> None:
        chosen = await self.push_screen_wait(ExportDialog())
        if chosen is None:
            return
        doc = self.document
        stem = doc.path.stem if doc.path else "untitled"
        default_dir = doc.path.parent if doc.path else self._save_base_dir()
        raw = await self.push_screen_wait(
            PathPrompt(
                f"Export {chosen.key.upper()} — where should it go?",
                initial=str(default_dir / f"{stem}{chosen.suffix}"),
                hint="Enter export · Esc cancel · ~ allowed",
            )
        )
        if raw is None:
            return
        out_path = resolve_save_path(raw, self._save_base_dir(), chosen.suffix)
        if out_path is None:
            self.notify("Empty path — nothing exported", severity="warning")
            return
        if out_path.exists():
            ok = await self.push_screen_wait(
                ConfirmDialog(
                    title="Overwrite existing file?",
                    message=f'"{out_path.name}" already exists.\nReplace it?',
                    yes_label="overwrite",
                    no_label="cancel",
                )
            )
            if not ok:
                self.notify("Export cancelled")
                return

        text = self._compiled_text()
        title = stem.replace("-", " ").replace("_", " ").strip() or "Untitled"
        self.notify(f"Exporting {chosen.key.upper()}…")
        # pandoc on a book takes seconds; keep it off the UI thread.
        ok, message = await asyncio.get_running_loop().run_in_executor(
            None, partial(export_document, text, out_path, chosen.key, title=title)
        )
        if ok:
            self.notify(f"Exported → {out_path.name}")
        else:
            self.notify(f"Export failed: {message}", severity="error", timeout=10)

    def cmd_compile(self) -> None:
        """Expand ``![[…]]`` includes of the active buffer into one Markdown file."""
        self.run_worker(self._compile_async())

    async def _compile_async(self) -> None:
        doc = self.document
        base_dir = doc.path.parent if doc.path else Path.cwd()
        resolve = make_resolver(self._project_root())
        output, errors = compile_document(
            doc.text, base_dir, resolve, self_path=doc.path
        )
        if doc.path is not None:
            default = str(doc.path.with_name(doc.path.stem + _COMPILED_SUFFIX))
        else:
            default = str(Path.cwd() / f"compiled{_DEFAULT_SUFFIX}")
        raw = await self.push_screen_wait(
            PathPrompt(
                "Compile — where should the combined Markdown go?",
                initial=default,
                hint="Enter save · Esc cancel · ~ allowed",
            )
        )
        if raw is None:
            return
        out_path = self._normalize_save_path(raw)
        if out_path is None:
            self.notify("Empty path — not compiled", severity="warning")
            return
        try:
            out_path.write_text(output, encoding="utf-8")
        except OSError as exc:
            self.notify(f"Compile failed: {exc}", severity="error")
            return
        if errors:
            self.notify(
                f"Compiled → {out_path.name} · {len(errors)} issue(s): {errors[0]}",
                severity="warning",
                timeout=8,
            )
        else:
            self.notify(f"Compiled → {out_path.name}")

    def action_bold(self) -> None:
        self.cmd_bold()

    def action_italic(self) -> None:
        self.cmd_italic()

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
        idx = word_left(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_word_right(self) -> None:
        idx = word_right(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_paragraph_up(self) -> None:
        idx = paragraph_up(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_paragraph_down(self) -> None:
        idx = paragraph_down(self.document.text, self._cursor_index())
        self._move_caret_to_index(idx)

    def action_move_line_up(self) -> None:
        """Swap the caret's line with the one above via a scoped editor edit, so
        undo/redo and the document sync work like every other edit (no full
        reload, no whole-document replace)."""
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        if row <= 0:
            return
        above = editor.document.get_line(row - 1)
        cur = editor.document.get_line(row)
        editor.replace(f"{cur}\n{above}", (row - 1, 0), (row, len(cur)))
        editor.move_cursor((row - 1, min(col, len(cur))))
        editor.focus()

    def action_move_line_down(self) -> None:
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        if row >= editor.document.line_count - 1:
            return
        cur = editor.document.get_line(row)
        below = editor.document.get_line(row + 1)
        editor.replace(f"{below}\n{cur}", (row, 0), (row + 1, len(below)))
        editor.move_cursor((row + 1, min(col, len(cur))))
        editor.focus()

    def action_duplicate_line(self) -> None:
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        cur = editor.document.get_line(row)
        editor.insert(f"\n{cur}", (row, len(cur)))
        editor.move_cursor((row + 1, col))
        editor.focus()

    def cmd_toggle_soft_wrap(self) -> None:
        editor = self.query_one("#editor", TextArea)
        editor.soft_wrap = not editor.soft_wrap
        self.prefs.soft_wrap = editor.soft_wrap
        self.prefs.save()
        self.notify(f"Soft wrap {'on' if editor.soft_wrap else 'off'}")

    def action_smart_copy(self) -> None:
        """Ctrl+C: copy from whichever text widget has focus. Never quits.

        Delegates to the focused TextArea/Input's own copy action; a bare
        Ctrl+C anywhere else is a quiet no-op (quit is Ctrl+Q).
        """
        focused = self.focused
        action = getattr(focused, "action_copy", None)
        if callable(action):
            action()

    def copy_to_clipboard(self, text: str) -> None:
        """Copy via OSC 52 (Textual) plus the OS-native clipboard tool.

        OSC 52 works in many terminals (Windows Terminal, kitty, Ghostty, …)
        but not all (VTE/GNOME Terminal ignores it), so we also pipe to the
        platform's native tool. Per-OS dispatch — each platform only ever
        invokes its own tool.
        """
        super().copy_to_clipboard(text)
        self._native_clipboard_copy(text)

    @staticmethod
    def _native_clipboard_copy(text: str) -> None:
        import os
        import shutil
        import subprocess

        if sys.platform == "win32":
            candidates = [["clip"]]  # ships with Windows
        elif sys.platform == "darwin":
            candidates = [["pbcopy"]]  # ships with macOS
        else:
            # Linux/BSD: prefer the tool matching the running session.
            candidates = []
            if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
                candidates.append(["wl-copy"])
            if os.environ.get("DISPLAY"):
                if shutil.which("xclip"):
                    candidates.append(["xclip", "-selection", "clipboard"])
                if shutil.which("xsel"):
                    candidates.append(["xsel", "--clipboard", "--input"])

        for cmd in candidates:
            try:
                subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                    check=True,
                )
                return
            except Exception:
                continue

    @staticmethod
    def _native_clipboard_paste() -> str | None:
        """Read the OS clipboard so Ctrl+V pastes what was copied in *other*
        apps too. Returns None if no native tool is available (callers then
        fall back to Textual's internal clipboard). Per-OS dispatch.
        """
        import os
        import shutil
        import subprocess

        if sys.platform == "win32":
            candidates = [["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]]
        elif sys.platform == "darwin":
            candidates = [["pbpaste"]]
        else:
            candidates = []
            if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
                candidates.append(["wl-paste", "--no-newline"])
            if os.environ.get("DISPLAY"):
                if shutil.which("xclip"):
                    candidates.append(["xclip", "-selection", "clipboard", "-o"])
                if shutil.which("xsel"):
                    candidates.append(["xsel", "--clipboard", "--output"])

        for cmd in candidates:
            try:
                out = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                    check=True,
                )
                text = out.stdout.decode("utf-8", "replace")
                # PowerShell's Get-Clipboard appends a trailing CRLF; trim one.
                if sys.platform == "win32":
                    text = text.rstrip("\r\n")
                return text
            except Exception:
                continue
        return None

    def cmd_toggle_mouse_capture(self) -> None:
        """Toggle terminal mouse tracking.

        Captured (default): MarkStar receives clicks/scroll/hover — but
        terminals without OSC 22 pointer support (e.g. VTE/GNOME Terminal)
        show an arrow pointer while any app tracks the mouse.
        Released: the terminal's native I-beam pointer and native text
        selection return; in-app clicking/scrolling/hover are off until
        re-enabled.
        """
        driver = self._driver
        if driver is None:
            return
        capturing = getattr(driver, "_mouse", True)
        if capturing:
            # Order matters: _disable_mouse_support() no-ops once _mouse is
            # False, so write the "off" sequences first, then latch the flag
            # (which also keeps suspend/resume from re-enabling tracking).
            try:
                driver._disable_mouse_support()
            except Exception:
                pass
            driver._mouse = False
            self.prefs.mouse = "off"
            self.prefs.save()
            self.notify(
                "Mouse released — native pointer & selection (View → Mouse Capture restores it)"
            )
        else:
            driver._mouse = True
            try:
                driver._enable_mouse_support()
            except Exception:
                pass
            self.prefs.mouse = "on"
            self.prefs.save()
            self.notify("Mouse captured — click, scroll, and hover enabled")

    # --- Autosave sidecars ---------------------------------------------------

    def _schedule_autosave(self) -> None:
        """Debounce a sidecar write after the last edit (default 1500 ms)."""
        if not self.prefs.autosave:
            return
        if self._autosave_timer is not None:
            self._autosave_timer.stop()
        delay = max(0.1, self.prefs.autosave_ms / 1000)
        self._autosave_timer = self.set_timer(delay, self._write_sidecar)

    def _write_sidecar(self) -> None:
        """Write the active buffer to its `.<name>.autosave` sidecar if dirty."""
        if not self.prefs.autosave:
            return
        doc = self.document
        if doc.path is not None and doc.dirty:
            write_sidecar(doc.path, doc.text)

    def cmd_toggle_autosave(self) -> None:
        self.prefs.autosave = not self.prefs.autosave
        self.prefs.save()
        if self.prefs.autosave:
            self._schedule_autosave()
        self.notify(f"Autosave {'on' if self.prefs.autosave else 'off'}")

    async def _maybe_restore(self, path: Path) -> None:
        """If a sidecar is newer than ``path``, offer to restore the unsaved work."""
        if not self.prefs.autosave or not sidecar_is_newer(path):
            return
        choice = await self.push_screen_wait(RestoreDialog(path.name))
        if choice == "discard":
            delete_sidecar(path)
            return
        if choice != "restore":
            return  # cancelled — leave the sidecar for next time
        text = read_sidecar(path)
        if text is None:
            return
        # Apply to the matching open buffer (it becomes dirty vs the file).
        for i, doc in enumerate(self.workspace.documents):
            if doc.path is not None and doc.path == path:
                self.workspace.set_active(i)
                doc.set_text(text)
                self._load_active_into_editor()
                self._refresh_status()
                self.notify(f"Restored unsaved changes to {path.name}")
                return

    # Spellcheck commands delegate to the SpellController (state + coordination).
    def cmd_suggest(self) -> None:
        self._spell.suggest()

    def _suggest_async(self, row, a, b, word, suggestions, off):
        # Thin passthrough kept for the existing tests; returns the coroutine.
        return self._spell.suggest_async(row, a, b, word, suggestions, off)

    def cmd_toggle_spellcheck(self) -> None:
        self._spell.toggle()

    def _schedule_spellcheck(self) -> None:
        self._spell.schedule()

    def _run_spellcheck(self) -> None:
        self._spell.run()

    def cmd_spelling(self) -> None:
        self._spell.start_walk()

    @on(SpellBar.SpellRequested)
    def _on_spell_requested(self, event: SpellBar.SpellRequested) -> None:
        self._spell.on_request(event.action, event.value)

    @on(SpellBar.Dismissed)
    def _on_spell_dismissed(self) -> None:
        self._spell.on_dismissed()

    def cmd_starbot_config(self) -> None:
        """Project → StarBot… — configure the AI assistant connection."""
        self.push_screen(StarBotConfigScreen())

    def cmd_toggle_starbot(self) -> None:
        """Ctrl+K — open/close the StarBot chat panel (right side)."""
        panel = self.query_one("#starbot-panel", StarBotPanel)
        if panel.is_open:
            panel.close()
            self.query_one("#editor", TextArea).focus()
        else:
            panel.open()
            panel.focus_input()
        self._update_prose_layout()

    def _starbot_open(self) -> bool:
        try:
            return self.query_one("#starbot-panel", StarBotPanel).is_open
        except Exception:
            return False

    @on(StarBotPanel.Submitted)
    def _on_starbot_submit(self, event: StarBotPanel.Submitted) -> None:
        panel = self.query_one("#starbot-panel", StarBotPanel)
        chat = self._ensure_starbot_chat(panel)
        if chat is None:
            return
        panel.add_user(event.text)
        self.run_worker(self._starbot_turn(chat, panel, event.text))

    def _ensure_starbot_chat(self, panel: StarBotPanel):
        """Build the chat (client + project tools) on first use; guide the user to
        configure a connection if there isn't one."""
        if self._starbot_chat is not None:
            return self._starbot_chat
        from markstar.ai.chat import StarBotChat
        from markstar.ai.client import OpenAIClient
        from markstar.ai.config import StarBotConfig
        from markstar.ai.tools import ProjectTools

        cfg = StarBotConfig.load()
        if not cfg.is_configured():
            panel.add_tool("no connection — set one up in Project → StarBot…")
            return None
        try:
            client = OpenAIClient(cfg)
        except Exception as exc:  # noqa: BLE001
            panel.add_tool(f"client error: {exc}")
            return None
        tools = ProjectTools(
            self._project_root(), on_proposal=self._on_starbot_proposal
        )
        self._starbot_chat = StarBotChat(client, tools=tools)
        return self._starbot_chat

    def _on_starbot_proposal(self, proposal) -> None:
        """StarBot proposed an edit — show a diff card the writer can act on."""
        try:
            panel = self.query_one("#starbot-panel", StarBotPanel)
        except Exception:
            return
        card = panel.add_edit_card(proposal)
        self._starbot_proposals[proposal.id] = (proposal, card)

    @on(EditCard.Accepted)
    def _on_edit_accepted(self, event: EditCard.Accepted) -> None:
        entry = self._starbot_proposals.get(event.proposal_id)
        if entry is None:
            return
        proposal, card = entry
        if self._apply_proposal(proposal):
            from markstar.ai.edits import ACCEPTED

            card.mark(ACCEPTED)

    @on(EditCard.Rejected)
    def _on_edit_rejected(self, event: EditCard.Rejected) -> None:
        entry = self._starbot_proposals.get(event.proposal_id)
        if entry is None:
            return
        from markstar.ai.edits import REJECTED

        entry[1].mark(REJECTED)

    def _apply_proposal(self, proposal) -> bool:
        """Apply an accepted edit to the file's editor buffer (undoable). Refuses
        if the target lines no longer match what StarBot saw (avoid clobbering)."""
        target = Path(self._project_root()) / proposal.path
        if not target.is_file():
            self.notify(f"Can't apply: {proposal.path} not found", severity="error")
            return False
        # Open the file so the change lands in the editor (visible + undoable).
        self.workspace.open_path(target)
        self._load_active_into_editor()
        editor = self.query_one("#editor", TextArea)
        doc = editor.document
        total = doc.line_count
        start, end = proposal.start_line, proposal.end_line
        if start < 1 or start > total:
            self.notify("Can't apply: line range no longer valid", severity="warning")
            return False
        end = min(end, total)
        current = "\n".join(doc.get_line(i) for i in range(start - 1, end))
        if proposal.old_text and current != proposal.old_text:
            self.notify(
                "The file changed since StarBot proposed this — not applied. "
                "Ask it to re-read and re-propose.",
                severity="warning",
            )
            return False
        end_line_text = doc.get_line(end - 1)
        editor.replace(proposal.new_text, (start - 1, 0), (end - 1, len(end_line_text)))
        editor.focus()
        self._refresh_status()
        self.notify(f"Applied StarBot's edit to {proposal.path}")
        return True

    async def _starbot_turn(self, chat, panel: StarBotPanel, text: str) -> None:
        panel.set_thinking(True)

        def emit(event) -> None:
            kind = event[0]
            if kind == "text":
                panel.append_assistant(event[1])
            elif kind == "tool":
                panel.add_tool(event[1])
            elif kind == "done":
                panel.finish_assistant()

        try:
            await chat.send(text, emit)
        except Exception as exc:  # noqa: BLE001 — surface any API/network error
            panel.add_tool(f"error: {exc}")
            panel.finish_assistant()
        self._save_starbot_transcript(chat)

    def _save_starbot_transcript(self, chat) -> None:
        """Persist the current conversation to the project's history folder."""
        from datetime import datetime

        from markstar.ai.history import ChatStore, ChatTranscript

        messages = getattr(chat, "messages", None)
        if not messages:
            return
        if self._starbot_transcript is None:
            now = datetime.now()
            self._starbot_transcript = ChatTranscript(
                id=now.strftime("%Y-%m-%dT%H-%M-%S"),
                created=now.isoformat(timespec="seconds"),
            )
        self._starbot_transcript.messages = list(messages)
        ChatStore(self._project_root()).save(self._starbot_transcript)

    def cmd_starbot_new_chat(self) -> None:
        """Start a fresh StarBot conversation (the old one stays saved)."""
        self._starbot_chat = None
        self._starbot_transcript = None
        self._starbot_proposals = {}
        panel = self.query_one("#starbot-panel", StarBotPanel)
        panel.clear()
        if not panel.is_open:
            panel.open()
            self._update_prose_layout()
        panel.focus_input()
        self.notify("New StarBot chat")

    def cmd_starbot_history(self) -> None:
        self.run_worker(self._starbot_history_async())

    async def _starbot_history_async(self) -> None:
        from markstar.ai.history import ChatStore
        from markstar.ui.starbot_history_screen import ChatHistoryScreen

        store = ChatStore(self._project_root())
        transcripts = store.list()
        if not transcripts:
            self.notify("No saved StarBot chats yet")
            return
        def _delete(tid: str) -> None:
            store.delete(tid)
            if self._starbot_transcript and self._starbot_transcript.id == tid:
                self._starbot_transcript = None  # was the active session's file

        chosen = await self.push_screen_wait(
            ChatHistoryScreen(transcripts, on_delete=_delete)
        )
        if not chosen:
            return
        transcript = store.load(chosen)
        if transcript is None:
            return
        panel = self.query_one("#starbot-panel", StarBotPanel)
        if not panel.is_open:
            panel.open()
            self._update_prose_layout()
        # Build a fresh chat and restore the saved history into it.
        self._starbot_chat = None
        chat = self._ensure_starbot_chat(panel)
        if chat is not None:
            chat.restore(transcript.messages)
        self._starbot_transcript = transcript
        panel.render_messages(transcript.messages)
        panel.focus_input()

    def cmd_toggle_zen(self) -> None:
        """Distraction-free: empty the tab ribbon and footer text (but keep their
        rule lines and dimensions so the prose frame stays put) and close the
        panel, leaving centered prose. (For a truly full-screen canvas, also
        toggle your terminal's fullscreen, usually F11 — the app can't drive that.)"""
        self._zen = not getattr(self, "_zen", False)
        # Hide only the *contents* — tab chips + footer hints/metrics — so the
        # top/bottom rule lines and overall dimensions are unchanged.
        for sel in ("#tab-label", "#support-hints", "#support-metrics"):
            try:
                self.query_one(sel).visible = not self._zen
            except Exception:
                pass
        if self._zen:
            try:
                panel = self.query_one("#project-panel", ProjectPanel)
                if panel.is_open:
                    panel.close()
            except Exception:
                pass
        self._update_prose_layout()
        try:
            self.query_one("#editor", TextArea).focus()
        except Exception:
            pass
        self.notify(f"Zen mode {'on' if self._zen else 'off'} — Esc for the menu")

    def cmd_toggle_line_numbers(self) -> None:
        """Show/hide the faint line-number gutter."""
        editor = self.query_one("#editor", MarkStarTextArea)
        self.prefs.line_numbers = not self.prefs.line_numbers
        editor.show_line_numbers = self.prefs.line_numbers
        self.prefs.save()
        # The gutter takes columns from the text area, so the writing measure
        # has to be recomputed or the prose shifts under the reader.
        self._update_prose_layout()
        self.notify(
            "Line numbers on" if self.prefs.line_numbers else "Line numbers off"
        )

    def cmd_toggle_center(self) -> None:
        """Toggle dynamic centering of the prose column."""
        self.prefs.center_text = not self.prefs.center_text
        self.prefs.save()
        self._update_prose_layout()
        self.notify(f"Center text {'on' if self.prefs.center_text else 'off'}")

    def cmd_toggle_formatting(self) -> None:
        """Toggle inline Markdown rendering (bold/italic/code shown vs. raw)."""
        editor = self.query_one("#editor", MarkStarTextArea)
        editor.set_render_markdown(not editor.render_markdown)
        self.prefs.formatting = editor.render_markdown
        self.prefs.save()
        self.notify(
            f"Formatting preview {'on' if editor.render_markdown else 'off'}"
        )

    def _sync_terminal_bg(self) -> None:
        """Tell the terminal to use our theme background as *its* default (OSC 11).

        A maximized window's height is rarely an exact multiple of the character
        cell height, so a thin sub-cell strip of the terminal's own default
        background shows below the last text row. The app can't paint pixels that
        aren't a character cell — but OSC 11 makes that strip match our bg instead
        of showing black. Portable xterm sequence (kitty/Ghostty/WezTerm/iTerm2/
        Windows Terminal/foot/GNOME honor it; others ignore it harmlessly).
        """
        try:
            bg = self.get_theme(self.theme).background
            drv = self._driver
            drv.write(_OSC_SET_BG.format(bg=bg))
            drv.flush()
        except Exception:
            pass

    def _reset_terminal_bg(self) -> None:
        """Restore the terminal's default background on exit (OSC 111)."""
        try:
            drv = self._driver
            drv.write(_OSC_RESET_BG)
            drv.flush()
        except Exception:
            pass

    def _apply_theme(self, name: str) -> None:
        """Switch to a theme and repaint everything that resolves theme tokens."""
        self.theme = name
        self._apply_editor_theme()
        self._sync_terminal_bg()
        try:
            self.query_one("#editor", MarkStarTextArea).refresh_theme_styles()
        except Exception:
            pass
        self._refresh_support_hints()
        self._refresh_status()
        for sel, cls in (("#find-bar", FindBar), ("#spell-bar", SpellBar)):
            try:
                self.query_one(sel, cls)._refresh_hints()
            except Exception:
                pass

    def cmd_theme_picker(self) -> None:
        """Open the theme picker with live preview (Enter keeps, Esc reverts)."""
        self.run_worker(self._theme_picker_async())

    async def _theme_picker_async(self) -> None:
        original = self.theme
        chosen = await self.push_screen_wait(
            ThemePicker(list(THEME_NAMES), original, self._apply_theme)
        )
        if chosen:
            self._apply_theme(chosen)
            self.prefs.theme = chosen
            self.prefs.save()
            self.notify(f"Theme: {chosen}")
        else:  # cancelled → revert the live preview
            self._apply_theme(original)

    def cmd_cycle_theme(self) -> None:
        """Rotate to the next registered theme (kept for a quick cycle)."""
        try:
            idx = THEME_NAMES.index(self.theme)
        except ValueError:
            idx = -1
        name = THEME_NAMES[(idx + 1) % len(THEME_NAMES)]
        self._apply_theme(name)
        self.prefs.theme = name
        self.prefs.save()
        self.notify(f"Theme: {name}")

    def cmd_about(self) -> None:
        self.notify(f"MarkStar {__version__} — markstar.studio · a Markdown-native homage to WordStar · MIT")

    def cmd_keyboard_shortcuts(self) -> None:
        """Open the keyboard reference (F1). Generated from the registry."""
        self.push_screen(HelpScreen(self.registry, __version__))

    def cmd_send_feedback(self) -> None:
        self.notify(
            "Feedback: daudzegir@gmail.com — I likely won't listen (but try anyway)",
            timeout=6,
        )

    @on(FindBar.Submitted)
    def _on_find_submitted(self, event: FindBar.Submitted) -> None:
        self._find.find(event.direction)

    @on(FindBar.Dismissed)
    def _on_find_dismissed(self) -> None:
        try:
            self.query_one("#editor", MarkStarTextArea).clear_search_highlights()
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
        self._find.on_query_changed(event.query)

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


def _terminal_renders_pointer_shapes() -> bool:
    """Best-effort: does this terminal honor OSC 22 pointer shapes?

    Not used for the mouse *default* (we always capture — see main), but tells
    us whether our ``pointer: text`` request will actually show an I-beam while
    captured (kitty/Ghostty/WezTerm/foot) vs. be ignored (VTE, conhost, …).
    Detection is by environment markers; no escape-sequence round-trip.
    """
    import os

    env = os.environ
    if env.get("KITTY_WINDOW_ID") or "kitty" in env.get("TERM", ""):
        return True
    if env.get("WEZTERM_PANE") or env.get("WEZTERM_EXECUTABLE"):
        return True
    if "ghostty" in env.get("TERM", "") or env.get("GHOSTTY_RESOURCES_DIR"):
        return True
    if env.get("TERM", "").startswith("foot"):
        return True
    return False


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="markstar", description="MarkStar — terminal Markdown word processor"
    )
    parser.add_argument("path", nargs="?", type=Path, help="Markdown file to open")
    mouse_group = parser.add_mutually_exclusive_group()
    mouse_group.add_argument(
        "--mouse",
        action="store_true",
        help="force mouse capture on (click-to-position, scroll, hover)",
    )
    mouse_group.add_argument(
        "--no-mouse",
        action="store_true",
        help="force mouse capture off (terminal-native I-beam pointer & selection)",
    )
    parser.add_argument("--version", action="version", version=f"MarkStar {__version__}")
    args = parser.parse_args(argv)

    prefs = Preferences.load()

    # Mouse capture: CLI flag wins for this run; else the saved pref; else the
    # default, which is ON everywhere — click-to-position, wheel-scrolls-view,
    # drag-select. (Capture OFF is the opt-in "native terminal I-beam &
    # selection" mode via --no-mouse / View > Mouse Capture / prefs.)
    if args.mouse:
        mouse = True
    elif args.no_mouse:
        mouse = False
    elif prefs.mouse == "off":
        mouse = False
    else:  # "on" or "auto" (default)
        mouse = True

    app = MarkStarApp(path=args.path, prefs=prefs)
    app.run(mouse=mouse)


if __name__ == "__main__":
    main(sys.argv[1:])

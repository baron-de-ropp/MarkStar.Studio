"""MarkStar TUI entrypoint (P0 shell + P1 commands / menus / find)."""

from __future__ import annotations

import argparse
import re
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

from markstar import __version__
from markstar.commands.registry import Command, CommandRegistry
from markstar.config import Preferences
from markstar.domain.document import Document
from markstar.domain.motion import paragraph_down, paragraph_up, word_left, word_right
from markstar.domain.search import (
    Match,
    find_all,
    find_next,
    replace_all,
    replace_match,
    step_find,
)
from markstar.domain.autosave import (
    delete_sidecar,
    read_sidecar,
    sidecar_is_newer,
    write_sidecar,
)
from markstar.domain.includes import compile_document, make_resolver
from markstar.domain.spellcheck import Speller, find_misspellings
from markstar.domain.workspace import Workspace
from markstar.ui.find_bar import FindBar
from markstar.ui.keys import normalize_key
from markstar.ui.menu_bar import MenuBar
from markstar.ui.project_panel import ProjectPanel, WriterTree
from markstar.ui.spell_bar import SpellBar
from markstar.ui.suggest_popup import SuggestPopup
from markstar.ui.theme_picker import ThemePicker
from markstar.ui.welcome import WelcomeScreen
from markstar.ui.themes import (
    ALL_THEMES,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    token,
)

# Inline Markdown patterns (approach #1: style spans, never hide characters, so
# there is no source↔screen offset mapping — see docs/MARKSTAR_KEYMAP.md §5b).
_RE_HEADING = re.compile(r"^(#{1,6}\s+)(.*)$")
_RE_QUOTE = re.compile(r"^(\s*>\s?)(.*)$")
# List marker at line start: -, +, * (bullet) or "1." (ordered), then a space.
# The trailing space distinguishes "* item" (bullet) from "*italic*".
_RE_LIST = re.compile(r"^(\s*(?:[-+*]|\d+\.)\s+)")
# [text](url) — dim the brackets/url, color the link text.
_RE_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")
# ![[name]] — a MarkStar include token (expanded only on compile).
_RE_INCLUDE = re.compile(r"!\[\[[^\]\n]+\]\]")
_RE_CODE = re.compile(r"`([^`\n]+)`")
_RE_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)")
_RE_STRIKE = re.compile(r"~~([^~\n]+)~~")
# A fenced-code delimiter line: ``` or ~~~ (3+), optionally indented, with an
# optional info string (language) after it. Fences span multiple lines, so they
# are tracked separately (see MarkStarTextArea._recompute_fences).
_RE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def _word_bounds(line: str, col: int) -> tuple[int, int]:
    """Expand ``col`` to the word (letters/digits/apostrophes) around it."""
    n = len(line)
    col = max(0, min(col, n))

    def is_word(ch: str) -> bool:
        return ch.isalnum() or ch == "'"

    start = col
    while start > 0 and is_word(line[start - 1]):
        start -= 1
    end = col
    while end < n and is_word(line[end]):
        end += 1
    return start, end


def _markdown_spans(line: str) -> list[tuple[int, int, str]]:
    """Return (start, end, style-key) spans for inline Markdown on one line.

    Markers (``**``, ``*``, `` ` ``, ``~~``, ``#``, ``>``) get the ``marker``
    key so they render dimmed; the wrapped content gets its semantic key.
    Characters are never removed, so columns map 1:1 to the document.
    (Fenced code blocks are handled per-line in get_line, not here.)
    """
    spans: list[tuple[int, int, str]] = []
    heading = _RE_HEADING.match(line)
    if heading:
        marker_end = len(heading.group(1))
        spans.append((0, marker_end, "marker"))
        spans.append((marker_end, len(line), "heading"))
        return spans
    quote = _RE_QUOTE.match(line)
    if quote:
        marker_end = len(quote.group(1))
        spans.append((0, marker_end, "marker"))
        spans.append((marker_end, len(line), "quote"))
        return spans
    # List marker (bullet/ordered): dim just the marker, then keep going so
    # inline formatting inside the item still renders.
    lst = _RE_LIST.match(line)
    if lst:
        spans.append((0, len(lst.group(1)), "marker"))
    # Includes: ![[name]] — a whole-token highlight (expanded only on compile).
    for m in _RE_INCLUDE.finditer(line):
        spans.append((m.start(), m.end(), "include"))
    # Links: [text](url) — color the text, dim the [] () and the url.
    for m in _RE_LINK.finditer(line):
        text_start = m.start() + 1
        text_end = text_start + len(m.group(1))
        spans.append((m.start(), text_start, "marker"))  # [
        spans.append((text_start, text_end, "link"))     # text
        spans.append((text_end, m.end(), "marker"))      # ](url)
    for rx, mlen, kind in (
        (_RE_CODE, 1, "code"),
        (_RE_BOLD, 2, "strong"),
        (_RE_ITALIC, 1, "emphasis"),
        (_RE_STRIKE, 2, "strike"),
    ):
        for m in rx.finditer(line):
            spans.append((m.start(), m.start() + mlen, "marker"))
            spans.append((m.start() + mlen, m.end() - mlen, kind))
            spans.append((m.end() - mlen, m.end(), "marker"))
    return spans


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

    # Base wrap_width already reserves the scrollbar column (via
    # scrollable_content_region) and 1 cursor cell; 3 more blank columns makes
    # the full 5-col right inset, so text ends at the same column as the rules
    # (which use `padding: 0 5`).
    EXTRA_RIGHT_MARGIN = 3

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
            if _RE_FENCE.match(line):
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
        return any(m.start() <= col < m.end() for m in _RE_LINK.finditer(line))

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
            a, b = _word_bounds(line, col)
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
                md_spans = _markdown_spans(text)
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


class _TabBar(Static):
    """The tab ribbon. Clicking a tab activates it; clicking its × closes it.

    Chip layout (plain): ``   {name} {•} × │`` — the app maps a click's column
    to a tab (and to the × hot-spot) via bounds computed in _refresh_status.
    """

    def on_click(self, event: events.Click) -> None:
        app = self.app
        if hasattr(app, "handle_tab_click"):
            app.handle_tab_click(event.x)  # type: ignore[attr-defined]


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

    # Matches design-spec prose measure / margin defaults (Preferences later).
    _PROSE_MARGIN_LEFT = 5
    _PROSE_MAX_WIDTH = 120

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
        self._syncing = False
        self.registry = CommandRegistry()
        self._last_find_end = 0
        # (start, end, close_col, index) per tab chip — for click routing.
        self._tab_bounds: list[tuple[int, int, int, int]] = []
        self._speller = Speller(self.prefs.spell_added)
        self._spellcheck_on = self.prefs.spellcheck
        self._spell_timer = None
        self._spell_current: tuple[int, int, str] | None = None
        self._autosave_timer = None
        self._build_commands()

    @property
    def document(self) -> Document:
        return self.workspace.active

    def _project_root(self) -> Path:
        """Root folder for the project panel: the opened file's dir, or cwd."""
        if self._path_arg is not None:
            try:
                return self._path_arg if self._path_arg.is_dir() else self._path_arg.parent
            except OSError:
                pass
        return Path.cwd()

    def _record_recent_project(self, root: Path) -> None:
        """Push a folder to the front of the recent-projects list (max 5)."""
        try:
            key = str(Path(root).expanduser().resolve())
        except Exception:
            return
        recents = [x for x in self.prefs.recent_projects if x != key]
        recents.insert(0, key)
        self.prefs.recent_projects = recents[:5]
        self.prefs.save()

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
        add("find_next", "Find Next", "Edit", self.cmd_find_next)  # Enter / ↓ in find bar
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
        add("next_tab", "Next Tab", "View", self.cmd_next_tab, "ctrl+pagedown")
        add("prev_tab", "Previous Tab", "View", self.cmd_prev_tab, "ctrl+pageup")
        add("toggle_soft_wrap", "Soft Wrap", "View", self.cmd_toggle_soft_wrap)  # menu
        add("toggle_center", "Center Text", "View", self.cmd_toggle_center)  # menu
        add("toggle_zen", "Zen Mode", "View", self.cmd_toggle_zen)  # menu
        add("toggle_spellcheck", "Spellcheck", "Tools", self.cmd_toggle_spellcheck)
        add("spelling", "Spelling…", "Tools", self.cmd_spelling)
        add("suggest", "Suggest Correction", "Tools", self.cmd_suggest, "ctrl+g")
        add("toggle_autosave", "Autosave", "Tools", self.cmd_toggle_autosave)
        add("toggle_formatting", "Formatting Preview", "View", self.cmd_toggle_formatting)
        add("theme_picker", "Theme…", "View", self.cmd_theme_picker)

        add("welcome", "Welcome…", "Help", self.cmd_welcome)
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
                yield _TabBar("", id="tab-label")  # chips built in _refresh_status
                # No blank row under the tab label — rule sits tight underneath
                yield Static("", id="tab-rule")
            yield FindBar(id="find-bar")
            yield SpellBar(id="spell-bar")
            with Horizontal(id="editor-row"):
                yield ProjectPanel(self._project_root(), id="project-panel")
                yield Static("", id="editor-left-pad")
                yield MarkStarTextArea(id="editor")
                yield Static("", id="editor-right-pad")
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
        editor.show_line_numbers = False
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

        if self._spellcheck_on:
            self.call_after_refresh(self._run_spellcheck)

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
            if theme_obj is not None:
                bg = theme_obj.background
                fg = theme_obj.foreground
                sel = theme_obj.variables.get("search-match", theme_obj.primary)
            else:
                bg, fg, sel = "#1E1E1E", "#D4D4D4", "#264F78"
            ed_name = f"ms-editor-{self.theme}"
            themed = dataclasses.replace(
                base,
                name=ed_name,
                base_style=Style(color=fg, bgcolor=bg),
                selection_style=Style(bgcolor=sel),
                cursor_line_style=Style(bgcolor=bg),
                gutter_style=Style(color=fg, bgcolor=bg),
                cursor_line_gutter_style=Style(color=fg, bgcolor=bg),
            )
            try:
                editor.register_theme(themed)
            except Exception:
                pass  # already registered under this name
            editor.theme = ed_name
        except Exception:
            pass

    def _compute_layout(self, width: int, panel_open: bool) -> tuple[int, int, int, int]:
        """Pure layout math → (panel_cols, left_pad, prose_cols, right_pad).

        The prose column lives to the RIGHT of the (overlay) panel and centers in
        the space that's left, so nothing is ever hidden under the panel. The
        panel is clamped so prose always keeps >= ~24 columns.
        """
        panel = 0
        if panel_open:
            panel = max(15, min(self.prefs.min_panel_width, width - 24))
            panel = max(0, panel)
        # The panel is an OVERLAY (its own layer) — it floats on top of the prose
        # and does NOT reserve width. So the prose column is always centered in the
        # full window; the panel simply covers whatever it covers. On a window too
        # narrow to clear it, the panel overlaps the text, which is acceptable.
        available = max(1, width)
        base = 5 if width >= 90 else 2
        if self.prefs.center_text:
            col = min(self.prefs.prose_width, max(1, available - 2 * base))
            side = max(base, (available - col) // 2)
        else:
            side = base
            col = max(1, available - 2 * base)
        left_pad = side
        right_pad = max(0, width - left_pad - col)
        return panel, left_pad, col, right_pad

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
        # Footer content sits 3 cols in (the tab chip's leading spaces).
        try:
            self.query_one("#support-row").styles.padding = (0, right_pad, 0, left_pad + 3)
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
        self.call_after_refresh(self._update_prose_rules)

    def _update_prose_rules(self, _retries: int = 0) -> None:
        """Fill top/bottom rules with ─ to match laid-out width (prose column)."""
        pending = False
        for rule_id in ("#status-rule", "#tab-rule"):
            try:
                rule = self.query_one(rule_id, Static)
            except Exception:
                continue
            # A hidden/undisplayed rule has no meaningful width — skip it rather
            # than wait for one. (Retrying forever on a permanently-zero-width
            # widget is a CPU-pegging repaint loop; that must never happen.)
            if not rule.display:
                continue
            # Use the widget's actual laid-out width so we track the prose surface
            width = max(1, rule.size.width)
            if width <= 1:
                pending = True
                continue
            rule.update("─" * width)
        # Layout not ready yet — retry next frame, but bounded (≈16 frames max).
        if pending and _retries < 16:
            self.call_after_refresh(lambda: self._update_prose_rules(_retries + 1))

    @on(TextArea.Changed)
    def _on_editor_changed(self, event: TextArea.Changed) -> None:
        if self._syncing:
            return
        new_text = event.text_area.text
        if new_text == self.document.text:
            return
        self.document.set_text(new_text)
        self._refresh_status()
        # Fenced code blocks are multi-line — recompute which lines are in a fence.
        if isinstance(event.text_area, MarkStarTextArea):
            event.text_area.recompute_fences()
        self._schedule_spellcheck()
        self._schedule_autosave()
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
        """Right-aligned stats, shortened on narrow terminals so they don't
        overflow the footer."""
        chars = len(self.document.text)
        words = self.document.word_count()
        width = self.size.width or 0
        if width < 66:
            text = f"{words}w"
        elif width < 92:
            text = f"{chars}c  │  {words}w"
        else:
            text = f"{chars} characters  │  {words} words  │  CommonMark"
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
        dim = token(self, "rule")
        chips: list[str] = []
        bounds: list[tuple[int, int, int, int]] = []
        cursor = 0
        active_index = self.workspace.active_index
        for i, doc in enumerate(self.workspace.documents):
            name = doc.path.name if doc.path else "Untitled"
            mid = "•" if doc.dirty else " "
            nc = (
                token(self, "tab-active")
                if i == active_index
                else token(self, "tab-inactive")
            )
            # Plain form: "   " + name + " " + mid + " " + "×" + " " + "│"
            chips.append(f"[{nc}]   {name} {mid} [/][{dim}]×[/] [{dim}]│[/]")
            width = len(name) + 9
            close_col = cursor + len(name) + 6
            bounds.append((cursor, cursor + width, close_col, i))
            cursor += width
        self._tab_bounds = bounds
        try:
            self.query_one("#tab-label", _TabBar).update("".join(chips))
        except Exception:
            pass

        self._refresh_metrics()
        self.call_after_refresh(self._update_prose_rules)
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

    def handle_tab_click(self, x: int) -> None:
        """Route a click in the tab ribbon: × closes that tab, else activates it."""
        for start, end, close_col, idx in self._tab_bounds:
            if start <= x < end:
                if x == close_col:
                    self._close_tab_index(idx)
                elif idx != self.workspace.active_index:
                    self._switch_tab(lambda i=idx: self.workspace.set_active(i))
                return

    def _close_tab_index(self, idx: int) -> None:
        self._sync_document_from_editor()
        if idx != self.workspace.active_index:
            self.workspace.set_active(idx)
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
        await self._maybe_restore(path)

    def cmd_toggle_project_panel(self) -> None:
        """Show/hide the left project-file overlay."""
        try:
            panel = self.query_one("#project-panel", ProjectPanel)
        except Exception:
            return
        if panel.is_open:
            panel.close()
            self.query_one("#editor", TextArea).focus()
        else:
            panel.open()
            panel.focus_tree()
        self._update_prose_layout()  # prose re-centers clear of the panel

    def action_toggle_project(self) -> None:
        self.cmd_toggle_project_panel()

    def cmd_welcome(self) -> None:
        """Re-open the welcome screen (Help > Welcome)."""
        self.run_worker(self._show_welcome())

    async def _show_welcome(self) -> None:
        recent = [Path(p) for p in self.prefs.recent_projects]
        root = await self.push_screen_wait(
            WelcomeScreen(self._project_root(), __version__, recent)
        )
        if root is None:
            return
        if root.is_dir():
            self._set_project_root(root)
        elif root.exists():
            self.notify(f'"{root.name}" is a file, not a folder', severity="warning")
        else:
            ok = await self.push_screen_wait(
                _ConfirmDialog(
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
            _PathPrompt(
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
        """Open the chosen file in a tab (keep the panel open for browsing)."""
        event.stop()
        self._sync_document_from_editor()
        try:
            self.workspace.open_path(Path(event.path))
        except OSError as exc:
            self.notify(f"Open failed: {exc}", severity="error")
            return
        self._last_find_end = 0
        self._load_active_into_editor()
        self._refresh_status()
        self.query_one("#editor", TextArea).focus()
        self.notify(f"Opened {Path(event.path).name}")
        self.run_worker(self._maybe_restore(Path(event.path)))

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
            # Explicit save → the sidecar is now stale; remove it.
            if self.document.path is not None:
                delete_sidecar(self.document.path)
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
                    title="Quit MarkStar?",
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
                self.notify(
                    "Enter a find string, then use Replace All",
                    severity="warning",
                )
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
        the caret — wrap if plain, strip the markers if already emphasized."""
        editor = self.query_one("#editor", TextArea)
        (sr, sc), (er, ec) = editor.selection.start, editor.selection.end
        if sr != er:  # multi-line selection → plain wrap (no toggle)
            self._wrap_selection(marker)
            return
        row = sr
        line = editor.document.get_line(row)
        mlen = len(marker)
        caret = editor.cursor_location[1]
        if sc != ec:
            a, b = sorted((sc, ec))
        else:
            a, b = _word_bounds(line, caret)

        enclosing = None
        for m in regex.finditer(line):
            if m.start() <= a and b <= m.end():
                enclosing = m
                break

        if enclosing is not None:  # already emphasized → strip markers
            s, e = enclosing.start(), enclosing.end()
            new_line = line[:s] + line[s + mlen : e - mlen] + line[e:]
            if caret <= s:
                nc = caret
            elif caret <= s + mlen:
                nc = s
            elif caret <= e - mlen:
                nc = caret - mlen
            else:
                nc = caret - 2 * mlen
        else:  # wrap the range (or insert empty markers at a bare caret)
            new_line = line[:a] + marker + line[a:b] + marker + line[b:]
            if caret <= a:
                nc = caret
            elif caret <= b:
                nc = caret + mlen
            else:
                nc = caret + 2 * mlen
        editor.replace(new_line, (row, 0), (row, len(line)))
        editor.move_cursor((row, max(0, min(nc, len(new_line)))))
        editor.focus()

    def cmd_bold(self) -> None:
        self._toggle_emphasis("**", _RE_BOLD)

    def cmd_italic(self) -> None:
        self._toggle_emphasis("*", _RE_ITALIC)

    def cmd_strikethrough(self) -> None:
        self._toggle_emphasis("~~", _RE_STRIKE)

    def cmd_inline_code(self) -> None:
        self._toggle_emphasis("`", _RE_CODE)

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

    def cmd_compile(self) -> None:
        """Expand ``![[…]]`` includes of the active buffer into one Markdown file."""
        self.run_worker(self._compile_async())

    async def _compile_async(self) -> None:
        self._sync_document_from_editor()
        doc = self.document
        base_dir = doc.path.parent if doc.path else Path.cwd()
        resolve = make_resolver(self._project_root())
        output, errors = compile_document(
            doc.text, base_dir, resolve, self_path=doc.path
        )
        if doc.path is not None:
            default = str(doc.path.with_name(doc.path.stem + ".compiled.md"))
        else:
            default = str(Path.cwd() / "compiled.md")
        raw = await self.push_screen_wait(
            _PathPrompt(
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
                "Mouse released — native pointer & selection (View menu re-enables)"
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
        self._sync_document_from_editor()
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
        choice = await self.push_screen_wait(_RestoreDialog(path.name))
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

    def cmd_suggest(self) -> None:
        """Pop a suggestion list at the caret for the misspelled word under it."""
        editor = self.query_one("#editor", MarkStarTextArea)
        row, col = editor.cursor_location
        line = editor.document.get_line(row)
        a, b = _word_bounds(line, col)
        if a == b:
            self.notify("Put the caret on a word first")
            return
        word = line[a:b]
        if self._speller.known(word):
            self.notify(f"“{word}” is spelled correctly")
            return
        suggestions = self._speller.suggestions(word)
        if not suggestions:
            self.notify(f"No suggestions for “{word}”")
            return
        off = editor.cursor_screen_offset
        self.run_worker(self._suggest_async(row, a, b, word, suggestions, off))

    async def _suggest_async(
        self, row, a, b, word, suggestions, off
    ) -> None:
        # Anchor just below the caret; flip above if it would run off the bottom.
        popup_h = min(len(suggestions) + 2, 12)
        y = off.y + 1
        if y + popup_h > self.size.height:
            y = max(0, off.y - popup_h)
        x = max(0, min(off.x, self.size.width - 42))
        chosen = await self.push_screen_wait(
            SuggestPopup(word, suggestions, (x, y))
        )
        if not chosen:
            return
        editor = self.query_one("#editor", TextArea)
        # Recompute the span (nothing else could edit while the modal was up).
        line = editor.document.get_line(row)
        if line[a:b] == word:
            editor.replace(chosen, (row, a), (row, b))
        editor.focus()

    def cmd_toggle_spellcheck(self) -> None:
        """Toggle underlining of misspelled words."""
        self._spellcheck_on = not self._spellcheck_on
        self.prefs.spellcheck = self._spellcheck_on
        self.prefs.save()
        if self._spellcheck_on:
            self._run_spellcheck()
        else:
            try:
                self.query_one("#editor", MarkStarTextArea).clear_spell_highlights()
            except Exception:
                pass
        self.notify(f"Spellcheck {'on' if self._spellcheck_on else 'off'}")

    def _schedule_spellcheck(self) -> None:
        """Debounce a re-check ~0.6s after the last edit."""
        if not self._spellcheck_on:
            return
        if self._spell_timer is not None:
            self._spell_timer.stop()
        self._spell_timer = self.set_timer(0.6, self._run_spellcheck)

    def _run_spellcheck(self) -> None:
        if not self._spellcheck_on:
            return
        text = self.document.text

        def work() -> None:
            # Dictionary loads lazily here — off the UI thread on first use.
            matches = find_misspellings(text, self._speller.known)
            self.call_from_thread(self._apply_spell, matches)

        self.run_worker(work, thread=True, exclusive=True, group="spell")

    def _apply_spell(self, matches: list[Match]) -> None:
        try:
            self.query_one("#editor", MarkStarTextArea).set_spell_highlights(matches)
        except Exception:
            pass

    # --- Interactive spelling (find-bar-style SpellBar) ----------------------

    def cmd_spelling(self) -> None:
        """Open the spelling bar and step to the first misspelling."""
        self._spell_goto(0)

    def _spell_goto(self, from_index: int) -> None:
        """Focus the first misspelling at/after ``from_index``; finish if none."""
        self._sync_document_from_editor()
        issues = find_misspellings(self.document.text, self._speller.known)
        try:
            self.query_one("#editor", MarkStarTextArea).set_spell_highlights(issues)
        except Exception:
            pass
        bar = self.query_one("#spell-bar", SpellBar)
        for i, m in enumerate(issues):
            if m.start >= from_index:
                word = self.document.text[m.start : m.end]
                self._spell_current = (m.start, m.end, word)
                self._select_range(m.start, m.end)
                bar.show_word(
                    word, self._speller.suggestions(word), i + 1, len(issues)
                )
                return
        # Nothing left from here.
        self._spell_current = None
        if bar.is_visible:
            bar.hide()
        self.notify(
            "No misspellings" if not issues else "Spelling check complete"
        )
        self.query_one("#editor", TextArea).focus()

    @on(SpellBar.SpellRequested)
    def _on_spell_requested(self, event: SpellBar.SpellRequested) -> None:
        if self._spell_current is None:
            return
        start, end, word = self._spell_current
        if event.action == "change":
            new = event.value
            editor = self.query_one("#editor", TextArea)
            try:
                s = editor.document.get_location_from_index(start)
                e = editor.document.get_location_from_index(end)
                editor.replace(new, s, e)
            except Exception:
                return
            self._spell_goto(start + len(new))
        elif event.action == "skip":
            self._speller.ignore(word)
            self._spell_goto(end)
        elif event.action == "add":
            self._speller.add(word)
            self.prefs.spell_added = self._speller.added_words
            self.prefs.save()
            self._spell_goto(end)

    @on(SpellBar.Dismissed)
    def _on_spell_dismissed(self) -> None:
        self._spell_current = None
        try:
            self.query_one("#editor", TextArea).focus()
        except Exception:
            pass

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
            drv.write(f"\x1b]11;{bg}\x07")
            drv.flush()
        except Exception:
            pass

    def _reset_terminal_bg(self) -> None:
        """Restore the terminal's default background on exit (OSC 111)."""
        try:
            drv = self._driver
            drv.write("\x1b]111\x07")
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
            editor = self.query_one("#editor", MarkStarTextArea)
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
            self.query_one("#editor", MarkStarTextArea).set_search_highlights(matches)
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


class _RestoreDialog(ModalScreen[str]):
    """Recover unsaved autosave work: Restore / Discard (Esc = decide later)."""

    CSS = """
    _RestoreDialog {
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
                f"[{hk}]R[/] restore  ·  [{hk}]D[/] discard  ·  [{hk}]Esc[/] decide later",
                id="restore-hint",
            )

    def action_restore(self) -> None:
        self.dismiss("restore")

    def action_discard(self) -> None:
        self.dismiss("discard")

    def action_later(self) -> None:
        self.dismiss("later")


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

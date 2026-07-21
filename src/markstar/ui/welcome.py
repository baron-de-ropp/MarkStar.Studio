"""Welcome screen — logo over a Works-style task launcher.

Shown at startup when MarkStar is launched with no file/folder, and re-summonable
from Help > Welcome. Three tabs (Recent Files / Projects / New) you arrow
through; nothing has to be typed. Returns a ``WelcomeChoice`` describing what the
writer picked, or None to drop into a blank document.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from markstar.domain.recent import abbreviate_dir, relative_age
from markstar.ui.path_input import PathInput

from markstar.ui.themes import token

# Tab order, left to right. Recent Files leads because reopening what you were
# writing yesterday is overwhelmingly the common case.
TAB_FILES, TAB_PROJECTS, TAB_NEW = "Recent Files", "Projects", "New"
_TABS = (TAB_FILES, TAB_PROJECTS, TAB_NEW)

_BROWSE_ID = "::browse"
_NEW_ID = "::new"
_SESSION_ID = "::session"

# Height of the reserved well under the tab strip, in rows: the tallest tab is
# Projects, at 7 list rows over a 3-row path field. Every tab gets all 10 so the
# logo above stays put; shorter tabs leave the remainder blank.
_FIELD_ROWS = 3
_WELL_ROWS = 7 + _FIELD_ROWS
# Floor for short terminals — below this the well shows too little to be worth
# reserving, and the hint line matters more.
_WELL_MIN_ROWS = 4


@dataclass(frozen=True)
class WelcomeChoice:
    """What the writer picked: open a file/folder, resume, start blank, or search."""

    kind: Literal["file", "folder", "new", "quick_open", "session"]
    path: Path | None = None

# ANSI Shadow "MARK" and "STAR", split so each word takes its own theme color.
_MARK = [
    "███╗   ███╗ █████╗ ██████╗ ██╗  ██╗",
    "████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝",
    "██╔████╔██║███████║██████╔╝█████╔╝ ",
    "██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ",
    "██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗",
    "╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
]
_STAR = [
    "███████╗████████╗ █████╗ ██████╗ ",
    "██╔════╝╚══██╔══╝██╔══██╗██╔══██╗",
    "███████╗   ██║   ███████║██████╔╝",
    "╚════██║   ██║   ██╔══██║██╔══██╗",
    "███████║   ██║   ██║  ██║██║  ██║",
    "╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝",
]

# Widest full-logo line, plus a little breathing room. Below this the big block
# wraps and looks broken, so we fall back to a one-line wordmark.
_LOGO_MIN_WIDTH = len(_MARK[0]) + len(_STAR[0]) + 4


class WelcomeScreen(ModalScreen[WelcomeChoice | None]):
    """Centered logo above a tabbed launcher. Enter opens, Esc starts blank."""

    CSS = """
    WelcomeScreen {
        align: center middle;
        background: $background;
    }
    #welcome-box {
        width: auto;
        max-width: 90%;
        height: auto;
        align: center top;
    }
    #welcome-logo {
        width: auto;
        content-align: center middle;
        padding: 0 0 1 0;
    }
    /* One-line wordmark on narrow terminals — span the box and center, give it
       weight + a little air. (width:auto would shrink to the text and left-align.) */
    #welcome-logo.compact {
        width: 100%;
        text-align: center;
        text-style: bold;
        padding: 1 0 1 0;
    }
    #welcome-tagline {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        padding: 0 0 2 0;
    }
    #welcome-tabs {
        width: 100%;
        text-align: center;
        padding: 0 0 1 0;
    }
    /* Fixed-height well for the list + path field. The three tabs hold wildly
       different amounts of content (one "Blank document" row vs. six projects
       and a path field), and with an auto height the box would grow and shrink
       — dragging the logo up and down every time you arrow between tabs. The
       height is the tallest case (7 list rows + a 3-row path field); shorter
       tabs simply leave the remainder blank. */
    #welcome-picker {
        width: 68;
        max-width: 100%;
        height: 10;
    }
    #welcome-folder {
        width: 100%;
        border: round $accent 50%;
        background: $surface;
        display: none;   /* only the Projects tab shows the path field */
    }
    #welcome-folder.shown {
        display: block;
    }
    #welcome-folder:focus {
        border: round $accent;
    }
    #recent-list {
        width: 100%;
        max-height: 7;
        border: none;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    #recent-list > .option-list--option-highlighted {
        background: $accent 45%;
        color: $text;
    }
    #welcome-hints {
        width: 100%;
        height: auto;
        color: $text-muted;
        padding: 2 0 0 0;
    }
    /* Wide: one centered line with all three hints. */
    #hints-wide {
        width: 100%;
        text-align: center;
        color: $text-muted;
    }
    /* Compact: two hints justified to the box edges, third centered underneath. */
    #hints-row {
        width: 100%;
        height: auto;
        display: none;
    }
    #hint-left {
        width: 1fr;
        text-align: left;
        color: $text-muted;
    }
    #hint-right {
        width: 1fr;
        text-align: right;
        color: $text-muted;
    }
    #hints-third {
        width: 100%;
        text-align: center;
        color: $text-muted;
        display: none;
    }
    #welcome-brand {
        dock: bottom;
        width: 100%;
        /* Per-line centering: name and "studio · version" each center on their
           own line (content-align would left-align the shorter second line). */
        text-align: center;
        color: $text-muted;
        padding: 0 0 0 0;
    }
    """

    BINDINGS = [
        Binding("escape", "skip", "Skip", show=False, priority=True),
    ]

    def __init__(
        self,
        default_dir: Path,
        version: str,
        recent: list[Path] | None = None,
        recent_files: list[tuple[Path, float]] | None = None,
        session_count: int = 0,
    ) -> None:
        super().__init__()
        self._default_dir = default_dir
        self._version = version
        self._recent = recent or []
        self._recent_files = recent_files or []
        self._session_count = session_count
        # First run has nothing to arrow through, so start where the writer can
        # actually do something: naming a project folder.
        self._tab = (
            TAB_FILES if (self._recent_files or session_count) else TAB_PROJECTS
        )

    def _logo_markup(self, compact: bool | None = None) -> str:
        mark = token(self.app, "md-heading")  # "MARK" — heading color
        star = token(self.app, "hint-key")    # "STAR" — accent
        if compact is None:
            compact = self._should_compact()
        if compact:
            # One-line wordmark for narrow terminals — the block logo would wrap.
            # MARK + STAR keep the same two theme colors as the full block logo.
            return f"[{mark}]MARK[/][{star}]STAR[/]"
        lines = [
            f"[{mark}]{m}[/][{star}]{s}[/]" for m, s in zip(_MARK, _STAR)
        ]
        return "\n".join(lines)

    def _should_compact(self) -> bool:
        try:
            return self.app.size.width < _LOGO_MIN_WIDTH
        except Exception:
            return False

    def _refresh_logo(self) -> None:
        compact = self._should_compact()
        try:
            logo = self.query_one("#welcome-logo", Static)
            logo.update(self._logo_markup(compact))
            logo.set_class(compact, "compact")
        except Exception:
            pass
        try:
            tagline = self.query_one("#welcome-tagline", Static)
            tagline.update(
                "markstar.studio"
                if compact
                else "A Markdown-native word processor  ·  markstar.studio"
            )
        except Exception:
            pass
        # Wide → single centered hint line; compact → justified row + centered third.
        for wid, show in (
            ("#hints-wide", not compact),
            ("#hints-row", compact),
            ("#hints-third", compact),
        ):
            try:
                self.query_one(wid).display = show
            except Exception:
                pass
        try:
            brand = self.query_one("#welcome-brand", Static)
            year = datetime.now().year
            if compact:
                # Two clean centered lines — no bullet to strand mid-wrap.
                brand.update(
                    f"© {year} Ryan Lewis Baron de Ropp\n"
                    f"markstar.studio  ·  v{self._version}"
                )
            else:
                brand.update(
                    f"© {year} Ryan Lewis Baron de Ropp    ·    "
                    f"markstar.studio    ·    v{self._version}"
                )
        except Exception:
            pass

    # ---- the reserved well -----------------------------------------------

    def _refresh_well(self) -> None:
        """Size the well to ``_WELL_ROWS``, shrinking it when the terminal is short.

        A fixed height is what stops the box breathing as you arrow between tabs,
        but held rigidly it would push the hint line — and the top of the logo —
        off a 24-row terminal. So it is a reservation, not a guarantee: measure
        what the rest of the box actually needs and give the well whatever is
        left, up to ``_WELL_ROWS``. Measuring beats a table of constants here
        because the chrome above it changes height with the compact logo.
        """
        try:
            well = self.query_one("#welcome-picker", Vertical)
            recent = self.query_one("#recent-list", OptionList)
        except Exception:
            return
        chrome = 0
        for sel in ("#welcome-logo", "#welcome-tagline", "#welcome-tabs",
                    "#welcome-hints", "#welcome-brand"):
            try:
                widget = self.query_one(sel)
            except Exception:
                continue
            if widget.display:
                chrome += widget.region.height
        if chrome <= 0:
            return  # pre-layout; on_mount's call_after_refresh will get it
        spare = self.app.size.height - chrome
        rows = max(_WELL_MIN_ROWS, min(_WELL_ROWS, spare))
        # Assigning is already change-guarded — Textual only relayouts when the
        # rule actually differs — so this is safe to call on every resize.
        well.styles.height = rows
        # The list must leave room for the path field below it, or a cramped
        # well would clip the field on the Projects tab — you'd be typing a
        # folder name into something you can't see.
        recent.styles.max_height = max(1, rows - _FIELD_ROWS)

    def on_resize(self, event: events.Resize) -> None:
        self._refresh_logo()
        # After the refresh, so the chrome is measured at its new size (the
        # compact logo and the two-line hints change height on narrow screens).
        self.call_after_refresh(self._refresh_well)

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-box"):
            yield Static(self._logo_markup(), id="welcome-logo", markup=True)
            yield Static("", id="welcome-tagline")
            yield Static(self._tabs_markup(), id="welcome-tabs", markup=True)
            with Vertical(id="welcome-picker"):
                yield OptionList(id="recent-list")
                yield PathInput(
                    value=str(self._default_dir),
                    placeholder="~/path/to/your/project  (Tab to complete)",
                    id="welcome-folder",
                )
            hk = token(self.app, "hint-key")
            # Each key+label is one unbreakable unit (nbsp within); groups are
            # separated by ordinary spaces so wrapping only happens *between*
            # hints, never splitting a key from its label ("Esc" | "skip").
            nb = " "
            def grp(key: str, label: str) -> str:
                return f"[{hk}]{key}[/]{nb}{label.replace(' ', nb)}"

            g_move = grp("↑↓", "choose")
            g_tabs = grp("←→", "tabs")
            g_open = grp("Enter", "open")
            g_new = grp("N", "new")
            g_find = grp("O", "open file")
            g_skip = grp("Esc", "blank")
            with Vertical(id="welcome-hints"):
                # Wide: everything on one centered line.
                yield Static(
                    f"{g_move}   {g_tabs}   {g_open}   {g_new}   {g_find}   {g_skip}",
                    id="hints-wide",
                    markup=True,
                )
                # Compact: two justified to the edges, the rest centered below.
                with Horizontal(id="hints-row"):
                    yield Static(g_move, id="hint-left", markup=True)
                    yield Static(g_tabs, id="hint-right", markup=True)
                yield Static(
                    f"{g_open}   {g_new}   {g_skip}", id="hints-third", markup=True
                )
        yield Static("", id="welcome-brand")

    def on_mount(self) -> None:
        self._refresh_logo()
        self._show_tab(self._tab)
        self.call_after_refresh(self._refresh_well)

    # ---- tabs ------------------------------------------------------------

    def _tabs_markup(self) -> str:
        """Active tab in the accent, the others dim — a text-only tab strip."""
        hk = token(self.app, "hint-key")
        dim = token(self.app, "rule")
        parts = []
        for name in _TABS:
            if name == self._tab:
                parts.append(f"[{hk}]▸ {name}[/]")
            else:
                parts.append(f"[{dim}]{name}[/]")
        return "   ".join(parts)

    def _show_tab(self, name: str) -> None:
        self._tab = name
        try:
            self.query_one("#welcome-tabs", Static).update(self._tabs_markup())
        except Exception:
            pass
        self._populate()

    def _cycle_tab(self, delta: int) -> None:
        i = (_TABS.index(self._tab) + delta) % len(_TABS)
        self._show_tab(_TABS[i])

    def _populate(self) -> None:
        try:
            ol = self.query_one("#recent-list", OptionList)
            folder = self.query_one("#welcome-folder", PathInput)
        except Exception:
            return
        ol.clear_options()
        dim = token(self.app, "rule")

        if self._tab == TAB_FILES:
            folder.set_class(False, "shown")
            if self._session_count:
                # Pinned above the MRU: picking up yesterday's whole desk beats
                # reopening one file at a time.
                plural = "s" if self._session_count != 1 else ""
                ol.add_option(
                    Option(
                        f"Continue where you left off   "
                        f"[{dim}]{self._session_count} file{plural}[/]",
                        id=_SESSION_ID,
                    )
                )
            if not self._recent_files and not self._session_count:
                ol.add_option(
                    Option("No recent files yet — O opens one, N starts blank",
                           disabled=True)
                )
            else:
                for path, mtime in self._recent_files:
                    ol.add_option(
                        Option(
                            f"{path.name}   [{dim}]{abbreviate_dir(path.parent)} · "
                            f"{relative_age(mtime)}[/]",
                            id=str(path),
                        )
                    )
        elif self._tab == TAB_PROJECTS:
            folder.set_class(True, "shown")
            for p in self._recent:
                ol.add_option(Option(self._recent_label(p), id=str(p)))
            ol.add_option(Option("Open another folder…", id=_BROWSE_ID))
        else:  # TAB_NEW
            folder.set_class(False, "shown")
            ol.add_option(Option("Blank document", id=_NEW_ID))

        if ol.option_count:
            ol.highlighted = 0
        # First run has an empty file list, so put the writer in the path field.
        if (
            self._tab == TAB_PROJECTS
            and not self._recent
            and not self._recent_files
            and not self._session_count
        ):
            folder.focus()
        else:
            ol.focus()

    # ---- selection -------------------------------------------------------

    def _recent_label(self, path: Path) -> str:
        name = path.name or str(path)
        dim = token(self.app, "rule")
        return f"{name}   [{dim}]{abbreviate_dir(path.parent)}[/]"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._confirm(event.value)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()
        chosen = event.option.id
        if not chosen:
            return
        if chosen == _SESSION_ID:
            self.dismiss(WelcomeChoice("session"))
        elif chosen == _NEW_ID:
            self.dismiss(WelcomeChoice("new"))
        elif chosen == _BROWSE_ID:
            self.query_one("#welcome-folder", PathInput).focus()
        elif self._tab == TAB_FILES:
            self.dismiss(WelcomeChoice("file", Path(chosen)))
        else:
            self.dismiss(WelcomeChoice("folder", Path(chosen)))

    def action_skip(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        # While the path field has focus it owns every printable key and the
        # arrows — only the list drives tabs and the letter shortcuts.
        typing = isinstance(self.focused, Input)
        if event.key in ("left", "right") and not typing:
            event.stop()
            event.prevent_default()
            self._cycle_tab(-1 if event.key == "left" else 1)
        elif event.key in ("n", "ctrl+n") and not typing:
            event.stop()
            self.dismiss(WelcomeChoice("new"))
        elif event.key == "o" and not typing:
            event.stop()
            self.dismiss(WelcomeChoice("quick_open"))
        elif event.key == "up" and typing:
            # Up out of the path field goes back to the list above it.
            event.stop()
            event.prevent_default()
            self.query_one("#recent-list", OptionList).focus()

    def _confirm(self, raw: str) -> None:
        # Return the path as-is; the app validates it exists (and offers to
        # create it as a new project if it doesn't).
        text = (raw or "").strip().strip('"').strip("'")
        if not text:
            self.dismiss(None)
            return
        self.dismiss(WelcomeChoice("folder", Path(text).expanduser()))

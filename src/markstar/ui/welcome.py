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


@dataclass(frozen=True)
class WelcomeChoice:
    """What the writer picked: open a file/folder, start blank, or search."""

    kind: Literal["file", "folder", "new", "quick_open"]
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
    #welcome-folder {
        width: 68;
        max-width: 100%;
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
        width: 68;
        max-width: 100%;
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
    ) -> None:
        super().__init__()
        self._default_dir = default_dir
        self._version = version
        self._recent = recent or []
        self._recent_files = recent_files or []
        # First run has nothing to arrow through, so start where the writer can
        # actually do something: naming a project folder.
        self._tab = TAB_FILES if self._recent_files else TAB_PROJECTS

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

    def on_resize(self, event: events.Resize) -> None:
        self._refresh_logo()

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-box"):
            yield Static(self._logo_markup(), id="welcome-logo", markup=True)
            yield Static("", id="welcome-tagline")
            yield Static(self._tabs_markup(), id="welcome-tabs", markup=True)
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
            if not self._recent_files:
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
        if self._tab == TAB_PROJECTS and not self._recent and not self._recent_files:
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
        if chosen == _NEW_ID:
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

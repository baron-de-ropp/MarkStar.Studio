"""Welcome screen — logo, project-folder chooser, quick tips (OpenCode energy).

Shown at startup when MarkStar is launched with no file/folder, and re-summonable
from Help > Welcome. Returns the chosen project folder (or None to skip).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from markstar.ui.themes import token

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


class WelcomeScreen(ModalScreen):
    """Centered logo + a folder path field. Enter confirms, Esc skips."""

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
    #welcome-prompt {
        width: 100%;
        content-align: center middle;
        color: $text;
        padding: 0 0 1 0;
    }
    #welcome-folder {
        width: 68;
        max-width: 100%;
        border: round $accent 50%;
        background: $surface;
    }
    #welcome-folder:focus {
        border: round $accent;
    }
    #recent-label {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        padding: 2 0 0 0;
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
        content-align: center middle;
        color: $text-muted;
        padding: 2 0 0 0;
    }
    #welcome-brand {
        dock: bottom;
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        padding: 0 0 0 0;
    }
    """

    BINDINGS = [
        Binding("escape", "skip", "Skip", show=False, priority=True),
    ]

    def __init__(
        self, default_dir: Path, version: str, recent: list[Path] | None = None
    ) -> None:
        super().__init__()
        self._default_dir = default_dir
        self._version = version
        self._recent = recent or []

    def _logo_markup(self, compact: bool | None = None) -> str:
        mark = token(self.app, "md-heading")  # "MARK" — heading color
        star = token(self.app, "hint-key")    # "STAR" — accent
        if compact is None:
            compact = self._should_compact()
        if compact:
            # One-line wordmark for narrow terminals — the block logo would wrap.
            return f"[{mark}]MARK[/][{star}]STAR ★[/]"
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
            yield Static("Choose your project folder", id="welcome-prompt")
            yield Input(
                value=str(self._default_dir),
                placeholder="~/path/to/your/project",
                id="welcome-folder",
            )
            if self._recent:
                yield Static("Recent projects", id="recent-label")
                options = [
                    Option(self._recent_label(p), id=str(p)) for p in self._recent
                ]
                yield OptionList(*options, id="recent-list")
            hk = token(self.app, "hint-key")
            # Each key+label is one unbreakable unit (nbsp within); groups are
            # separated by ordinary spaces so wrapping only happens *between*
            # hints, never splitting a key from its label ("Esc" | "skip").
            nb = " "
            hints = [
                (f"[{hk}]Enter[/]", "open folder"),
                (f"[{hk}]Ctrl+N[/]", "new file"),
                (f"[{hk}]Esc[/]", "skip"),
            ]
            groups = [f"{key}{nb}{label.replace(' ', nb)}" for key, label in hints]
            yield Static("   ".join(groups), id="welcome-hints")
        yield Static("", id="welcome-brand")

    def on_mount(self) -> None:
        self._refresh_logo()
        self.query_one("#welcome-folder", Input).focus()

    def _recent_label(self, path: Path) -> str:
        name = path.name or str(path)
        try:
            parent = str(path.parent)
        except Exception:
            parent = ""
        return f"{name}   [dim]{parent}[/]"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._confirm(event.value)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()
        if event.option.id:
            self.dismiss(Path(event.option.id))

    def action_skip(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        # Ctrl+N from the welcome screen = skip into a fresh buffer.
        if event.key == "ctrl+n":
            event.stop()
            self.dismiss(None)

    def _confirm(self, raw: str) -> None:
        # Return the path as-is; the app validates it exists (and offers to
        # create it as a new project if it doesn't).
        text = (raw or "").strip().strip('"').strip("'")
        if not text:
            self.dismiss(None)
            return
        self.dismiss(Path(text).expanduser())

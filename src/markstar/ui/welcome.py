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

    def _logo_markup(self) -> str:
        mark = token(self.app, "md-heading")  # "MARK" — heading color
        star = token(self.app, "hint-key")    # "STAR" — accent
        lines = [
            f"[{mark}]{m}[/][{star}]{s}[/]" for m, s in zip(_MARK, _STAR)
        ]
        return "\n".join(lines)

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-box"):
            yield Static(self._logo_markup(), id="welcome-logo", markup=True)
            yield Static(
                "A Markdown-native word processor  ·  markstar.studio",
                id="welcome-tagline",
            )
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
            yield Static(
                f"[{hk}]Enter[/] open folder    "
                f"[{hk}]Ctrl+N[/] new file    "
                f"[{hk}]Esc[/] skip",
                id="welcome-hints",
            )
        year = datetime.now().year
        yield Static(
            f"© {year} Ryan Lewis Baron de Ropp    ·    "
            f"markstar.studio    ·    v{self._version}",
            id="welcome-brand",
        )

    def on_mount(self) -> None:
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
        text = (raw or "").strip().strip('"').strip("'")
        if not text:
            self.dismiss(None)
            return
        path = Path(text).expanduser()
        if not path.is_dir():
            self.notify(f"Not a folder: {path}", severity="warning")
            return
        self.dismiss(path)

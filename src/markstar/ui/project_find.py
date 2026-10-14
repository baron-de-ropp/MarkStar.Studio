"""Project-wide find / replace modal (F8).

Find walks every document under the project root; Replace All writes the
substitution to disk after the app has saved dirty tabs. Results reuse the
existing FindResultsScreen.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from markstar.ui.themes import token


class ProjectFindReplaceScreen(ModalScreen[tuple[str, str, str] | None]):
    """Dismisses with ``(action, query, replacement)`` or None.

    ``action`` is ``"find"`` or ``"replace_all"``. Empty query cancels.
    """

    CSS = """
    ProjectFindReplaceScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #pf-panel {
        width: 72;
        max-width: 94%;
        height: auto;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #pf-title { text-style: bold; color: $text; padding-bottom: 1; }
    #pf-find, #pf-replace { width: 100%; }
    #pf-label-find, #pf-label-replace { color: $text-muted; padding-top: 1; }
    #pf-hint { color: $text-muted; padding-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("enter", "find", show=False, priority=True),
        Binding("ctrl+l", "replace_all", show=False, priority=True),
    ]

    def __init__(
        self,
        project_name: str,
        *,
        initial_query: str = "",
        initial_replace: str = "",
    ) -> None:
        super().__init__()
        self._project_name = project_name
        self._initial_query = initial_query
        self._initial_replace = initial_replace

    def compose(self) -> ComposeResult:
        hk = token(self.app, "hint-key")
        with Vertical(id="pf-panel"):
            yield Label(
                f"Find / Replace in {self._project_name}",
                id="pf-title",
            )
            yield Label("Find", id="pf-label-find")
            yield Input(
                value=self._initial_query,
                placeholder="text to find",
                id="pf-find",
            )
            yield Label("Replace with", id="pf-label-replace")
            yield Input(
                value=self._initial_replace,
                placeholder="replacement (for Replace All)",
                id="pf-replace",
            )
            yield Label(
                f"[{hk}]Enter[/] find  ·  [{hk}]Ctrl+L[/] replace all  ·  "
                f"[{hk}]Esc[/] cancel",
                id="pf-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#pf-find", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_find(self) -> None:
        query = self.query_one("#pf-find", Input).value
        if not query:
            return
        replacement = self.query_one("#pf-replace", Input).value
        self.dismiss(("find", query, replacement))

    def action_replace_all(self) -> None:
        query = self.query_one("#pf-find", Input).value
        if not query:
            return
        replacement = self.query_one("#pf-replace", Input).value
        self.dismiss(("replace_all", query, replacement))

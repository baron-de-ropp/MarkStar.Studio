"""Find / replace bar — compact strip under the tab rule (VS Code–like)."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Static

from prose.ui.keys import is_replace_all_key, normalize_key


class FindInput(Input):
    """Find/replace field with keys chosen for terminal reliability.

    - Enter in the *find* field → next match
    - Enter in the *replace* field → replace one
    - Ctrl+Enter → previous match (needs a terminal that reports the chord)
    - Ctrl+R → expand to replace (handled on FindBar / App)
    """

    async def _on_key(self, event: events.Key) -> None:
        bar = self._find_bar()
        if bar is None:
            await super()._on_key(event)
            return

        key = normalize_key(event.key)

        if key in {"enter", "return"}:
            event.prevent_default()
            event.stop()
            if self.id == "replace-input" and bar.is_replace_mode:
                bar.post_message(FindBar.ReplaceRequested("one"))
            else:
                bar.post_message(FindBar.Submitted("next"))
            return

        if key in {"ctrl+enter"}:
            event.prevent_default()
            event.stop()
            bar.post_message(FindBar.Submitted("prev"))
            return

        if key in {"ctrl+r", "ctrl+h"}:
            # ctrl+h only when the terminal reports it as ctrl+h (not Backspace).
            event.prevent_default()
            event.stop()
            bar.expand_replace()
            return

        if is_replace_all_key(key):
            event.prevent_default()
            event.stop()
            # Always request replace-all; app ensures bar/query state.
            if not bar.is_replace_mode:
                bar.expand_replace()
            bar.post_message(FindBar.ReplaceRequested("all"))
            return

        await super()._on_key(event)

    def _find_bar(self) -> FindBar | None:
        node = self.parent
        while node is not None:
            if isinstance(node, FindBar):
                return node
            node = node.parent
        return None


class FindBar(Vertical):
    """Top-of-prose-frame find UI.

    Ctrl+F opens find; Ctrl+R opens/expands replace.
    Enter = next (find field) or replace one (replace field).
    Ctrl+Enter = previous when the terminal delivers it.
    Ctrl+Alt+R = replace all (bulk / whole-document chord).
    """

    DEFAULT_CSS = """
    FindBar {
        height: auto;
        width: 100%;
        display: none;
        background: $boost;
        padding: 0 5;
        border-bottom: solid $accent 30%;
    }

    FindBar.visible {
        display: block;
    }

    FindBar #find-row, FindBar #replace-row {
        height: 1;
        width: 100%;
        margin: 0;
        padding: 0;
    }

    FindBar #find-hint-row {
        height: 1;
        width: 100%;
        color: $text-muted;
    }

    FindBar .find-label {
        width: 8;
        height: 1;
        color: $text-muted;
        padding: 0 1 0 0;
        content-align: left middle;
    }

    FindBar Input {
        width: 1fr;
        height: 1;
        border: none;
        padding: 0 1;
        background: $panel;
        color: $text;
    }

    FindBar Input:focus {
        border: none;
        background: $panel;
        background-tint: $accent 15%;
    }

    FindBar #find-count {
        width: auto;
        min-width: 8;
        height: 1;
        color: $text-muted;
        text-align: right;
        padding: 0 0 0 1;
    }

    FindBar #find-hints {
        width: 1fr;
        height: 1;
        color: $text-muted;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False, priority=True),
        Binding("enter", "submit_enter", "Next / Replace", show=False, priority=True),
        Binding("ctrl+enter", "find_prev", "Previous", show=False, priority=True),
        Binding("ctrl+r", "expand_replace", "Replace mode", show=False, priority=True),
        # Only fires when the terminal sends a real ctrl+h (not ASCII BS).
        Binding("ctrl+h", "expand_replace", "Replace mode", show=False, priority=True),
        Binding("ctrl+alt+r", "replace_all", "Replace all", show=False, priority=True),
        Binding("alt+ctrl+r", "replace_all", "Replace all", show=False, priority=True),
        Binding("ctrl+alt+R", "replace_all", "Replace all", show=False, priority=True),
        Binding("alt+ctrl+R", "replace_all", "Replace all", show=False, priority=True),
    ]

    class Submitted(Message):
        def __init__(self, direction: str) -> None:
            super().__init__()
            self.direction = direction  # "next" | "prev"

    class Dismissed(Message):
        pass

    class ExpandReplace(Message):
        """User asked to expand the find bar into find+replace."""

    class ReplaceRequested(Message):
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode  # "one" | "all"

    class QueryChanged(Message):
        """Find string changed — parent can refresh match count / live-seek."""

        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    def __init__(self, *args, show_replace: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._show_replace = show_replace

    def compose(self) -> ComposeResult:
        with Horizontal(id="find-row"):
            yield Static("Find", classes="find-label", id="find-label")
            yield FindInput(
                placeholder="Find…",
                id="find-input",
                classes="-textual-compact",
            )
            yield Static("", id="find-count")
        with Horizontal(id="replace-row"):
            yield Static("Replace", classes="find-label", id="replace-label")
            yield FindInput(
                placeholder="Replace with…",
                id="replace-input",
                classes="-textual-compact",
            )
        with Horizontal(id="find-hint-row"):
            yield Static("", id="find-hints")

    def on_mount(self) -> None:
        self._apply_replace_visibility()
        self._refresh_hints()

    def show(self, *, replace: bool = False, seed: str | None = None) -> None:
        """Reveal the bar; optionally seed the find field (e.g. current selection)."""
        already_open = self.is_visible
        self._show_replace = replace
        self._apply_replace_visibility()
        self._refresh_hints()
        self.add_class("visible")
        find_input = self.query_one("#find-input", FindInput)
        if seed is not None:
            find_input.value = seed
            find_input.cursor_position = len(seed)
            self.post_message(self.QueryChanged(seed))
        if replace and (already_open or bool(find_input.value)):
            self.query_one("#replace-input", FindInput).focus()
        else:
            find_input.focus()

    def expand_replace(self) -> None:
        """Show the replace row and focus the replacement field (keep find text)."""
        self._show_replace = True
        self._apply_replace_visibility()
        self._refresh_hints()
        self.add_class("visible")
        self.query_one("#replace-input", FindInput).focus()
        self.post_message(self.ExpandReplace())

    def hide(self) -> None:
        self.remove_class("visible")
        self.post_message(self.Dismissed())

    @property
    def is_visible(self) -> bool:
        return self.has_class("visible")

    @property
    def is_replace_mode(self) -> bool:
        return self._show_replace

    @property
    def query(self) -> str:
        return self.query_one("#find-input", FindInput).value

    @property
    def replacement(self) -> str:
        return self.query_one("#replace-input", FindInput).value

    def set_match_count(self, current: int | None, total: int) -> None:
        """Update the ``2/5`` counter. ``current`` is 1-based; None → no current."""
        label = self.query_one("#find-count", Static)
        if not self.query:
            label.update("")
            return
        if total == 0:
            label.update("0/0")
            return
        if current is None:
            label.update(f"?/{total}")
        else:
            label.update(f"{current}/{total}")

    def action_dismiss(self) -> None:
        self.hide()

    def action_submit_enter(self) -> None:
        """Enter when focus is on the bar but not always on FindInput."""
        focused = self.app.focused
        if (
            self._show_replace
            and isinstance(focused, FindInput)
            and focused.id == "replace-input"
        ):
            self.post_message(self.ReplaceRequested("one"))
        else:
            self.post_message(self.Submitted("next"))

    def action_find_prev(self) -> None:
        self.post_message(self.Submitted("prev"))

    def action_expand_replace(self) -> None:
        self.expand_replace()

    def action_replace_all(self) -> None:
        if not self._show_replace:
            self.expand_replace()
        self.post_message(self.ReplaceRequested("all"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Fallback if Enter slips through as Input.Submitted."""
        event.stop()
        if event.input.id == "replace-input" and self._show_replace:
            self.post_message(self.ReplaceRequested("one"))
        else:
            self.post_message(self.Submitted("next"))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "find-input":
            self.post_message(self.QueryChanged(event.value))

    def _apply_replace_visibility(self) -> None:
        row = self.query_one("#replace-row", Horizontal)
        row.display = self._show_replace

    def _refresh_hints(self) -> None:
        if self._show_replace:
            text = (
                "[#007ACC]Enter[/] replace/next  "
                "[#007ACC]Ctrl+Enter[/] prev  "
                "[#007ACC]Ctrl+Alt+R[/] all  "
                "[#007ACC]Esc[/] close"
            )
        else:
            text = (
                "[#007ACC]Enter[/] next  "
                "[#007ACC]Ctrl+Enter[/] prev  "
                "[#007ACC]Ctrl+R[/] replace  "
                "[#007ACC]Esc[/] close"
            )
        try:
            self.query_one("#find-hints", Static).update(text)
        except Exception:
            pass

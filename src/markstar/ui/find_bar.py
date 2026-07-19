"""Find / replace bar — compact strip under the tab rule (VS Code–like)."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Static

from markstar.ui.keys import normalize_key
from markstar.ui.themes import token


class FindInput(Input):
    """Find/replace field. Key commands (all single-stroke, terminal-safe):

    - Enter (find field) → next match ·  Enter (replace field) → replace one
    - ↓ → next match ·  ↑ → previous match
    - Ctrl+L → Replace All  (only in replace mode; "L" = aLL — Ctrl+A is
      Select All everywhere, far too dangerous to repurpose)
    - Ctrl+R → expand find into replace
    """

    async def _on_key(self, event: events.Key) -> None:
        bar = self._find_bar()
        if bar is None:
            await super()._on_key(event)
            return

        key = normalize_key(event.key)

        # Ctrl+L = Replace All (deliberately NOT Ctrl+A, which is Select All).
        if key == "ctrl+l" and bar.is_replace_mode:
            event.prevent_default()
            event.stop()
            bar.post_message(FindBar.ReplaceRequested("all"))
            return

        if key in {"enter", "return"}:
            event.prevent_default()
            event.stop()
            if self.id == "replace-input" and bar.is_replace_mode:
                bar.post_message(FindBar.ReplaceRequested("one"))
            else:
                bar.post_message(FindBar.Submitted("next"))
            return

        # Arrow keys cycle matches — a single-line Input ignores up/down anyway.
        if key == "down":
            event.prevent_default()
            event.stop()
            bar.post_message(FindBar.Submitted("next"))
            return

        if key == "up":
            event.prevent_default()
            event.stop()
            bar.post_message(FindBar.Submitted("prev"))
            return

        if key == "ctrl+r":
            event.prevent_default()
            event.stop()
            bar.expand_replace()
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
    Enter / ↓ = next · ↑ = previous · Enter (replace field) = replace one ·
    Ctrl+L = Replace All. (Replace All also lives in the Edit menu.)
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
        Binding("ctrl+r", "expand_replace", "Replace mode", show=False, priority=True),
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

    def action_expand_replace(self) -> None:
        self.expand_replace()

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
        # Footer-style: [blue]KEY[/] Action, joined by "  |  ".
        # Both modes share the same shape: Enter · ↑↓ · one Ctrl command · Esc.
        if self._show_replace:
            parts = [
                ("Enter", "Replace & Next"),
                ("↑↓", "Prev/Next"),
                ("Ctrl+L", "Replace All"),
                ("Esc", "Close"),
            ]
        else:
            parts = [
                ("Enter", "Next"),
                ("↑↓", "Prev/Next"),
                ("Ctrl+R", "Replace"),
                ("Esc", "Close"),
            ]
        hk = token(self.app, "hint-key", "#007ACC")
        text = "  |  ".join(f"[{hk}]{key}[/] {desc}" for key, desc in parts)
        try:
            self.query_one("#find-hints", Static).update(text)
        except Exception:
            pass

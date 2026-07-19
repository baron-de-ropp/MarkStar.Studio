"""Spelling bar — find/replace-style strip for walking misspellings.

Mirrors the find/replace bar's interface and key feel: a top-of-frame strip
that steps through misspelled words. The app drives navigation (it owns the
document + speller); this widget just displays the current word + a suggestion
field and posts the chosen action.

Keys (in the Fix field):
    Enter    change the word to the Fix text, advance
    ↑ / ↓    cycle through suggestions into the Fix field
    Ctrl+G   skip this word (ignore for the session), advance
    Ctrl+D   add the word to your dictionary, advance
    Esc      close
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Static

from markstar.ui.keys import normalize_key
from markstar.ui.themes import token


class SpellInput(Input):
    """Fix field. Enter=change, ↑↓=cycle suggestions, Ctrl+G=skip, Ctrl+D=add."""

    async def _on_key(self, event: events.Key) -> None:
        bar = self._spell_bar()
        if bar is None:
            await super()._on_key(event)
            return
        key = normalize_key(event.key)
        if key in {"enter", "return"}:
            event.prevent_default()
            event.stop()
            bar.post_message(SpellBar.SpellRequested("change", self.value))
            return
        if key == "down":
            event.prevent_default()
            event.stop()
            bar.cycle_suggestion(1)
            return
        if key == "up":
            event.prevent_default()
            event.stop()
            bar.cycle_suggestion(-1)
            return
        if key == "ctrl+g":
            event.prevent_default()
            event.stop()
            bar.post_message(SpellBar.SpellRequested("skip", ""))
            return
        if key == "ctrl+d":
            event.prevent_default()
            event.stop()
            bar.post_message(SpellBar.SpellRequested("add", ""))
            return
        await super()._on_key(event)

    def _spell_bar(self) -> "SpellBar | None":
        node = self.parent
        while node is not None:
            if isinstance(node, SpellBar):
                return node
            node = node.parent
        return None


class SpellBar(Vertical):
    """Top-of-prose-frame spelling strip."""

    DEFAULT_CSS = """
    SpellBar {
        height: auto;
        width: 100%;
        display: none;
        background: $boost;
        padding: 0 5;
        border-bottom: solid $accent 30%;
    }
    SpellBar.visible { display: block; }
    SpellBar #spell-word-row, SpellBar #spell-fix-row, SpellBar #spell-hint-row {
        height: 1;
        width: 100%;
    }
    SpellBar .spell-label {
        width: 12;
        height: 1;
        color: $text-muted;
        content-align: left middle;
    }
    SpellBar #spell-word {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }
    SpellBar #spell-count {
        width: auto;
        min-width: 8;
        height: 1;
        color: $text-muted;
        text-align: right;
    }
    SpellBar SpellInput {
        width: 1fr;
        height: 1;
        border: none;
        padding: 0 1;
        background: $background;
        color: $text;
    }
    SpellBar SpellInput:focus {
        border: none;
        background: $background;
        background-tint: $accent 15%;
    }
    SpellBar #spell-hints {
        width: 1fr;
        height: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False, priority=True),
        Binding("enter", "submit", "Change", show=False, priority=True),
    ]

    class SpellRequested(Message):
        def __init__(self, action: str, value: str) -> None:
            super().__init__()
            self.action = action  # "change" | "skip" | "add"
            self.value = value

    class Dismissed(Message):
        pass

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._suggestions: list[str] = []
        self._sugg_index = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="spell-word-row"):
            yield Static("Not in Dict", classes="spell-label")
            yield Static("", id="spell-word")
            yield Static("", id="spell-count")
        with Horizontal(id="spell-fix-row"):
            yield Static("Suggestion", classes="spell-label")
            yield SpellInput(id="spell-fix", classes="-textual-compact")
        with Horizontal(id="spell-hint-row"):
            yield Static("", id="spell-hints")

    def on_mount(self) -> None:
        self._refresh_hints()

    @property
    def is_visible(self) -> bool:
        return self.has_class("visible")

    def show_word(
        self, word: str, suggestions: list[str], position: int, total: int
    ) -> None:
        """Display the current misspelling + suggestions and focus the Fix field."""
        self._suggestions = suggestions
        self._sugg_index = 0
        spell = token(self.app, "spell-underline")
        self.query_one("#spell-word", Static).update(f"[{spell} u]{word}[/]")
        self.query_one("#spell-count", Static).update(f"{position}/{total}")
        fix = self.query_one("#spell-fix", SpellInput)
        fix.value = suggestions[0] if suggestions else word
        fix.cursor_position = len(fix.value)
        self.add_class("visible")
        self._refresh_hints()
        fix.focus()

    def cycle_suggestion(self, step: int) -> None:
        if not self._suggestions:
            return
        self._sugg_index = (self._sugg_index + step) % len(self._suggestions)
        fix = self.query_one("#spell-fix", SpellInput)
        fix.value = self._suggestions[self._sugg_index]
        fix.cursor_position = len(fix.value)

    def hide(self) -> None:
        self.remove_class("visible")
        self.post_message(self.Dismissed())

    def action_dismiss(self) -> None:
        self.hide()

    def action_submit(self) -> None:
        value = self.query_one("#spell-fix", SpellInput).value
        self.post_message(self.SpellRequested("change", value))

    def _refresh_hints(self) -> None:
        hk = token(self.app, "hint-key")
        parts = [
            ("Enter", "Change"),
            ("↑↓", "Suggestions"),
            ("Ctrl+G", "Skip"),
            ("Ctrl+D", "Add"),
            ("Esc", "Close"),
        ]
        text = "  |  ".join(f"[{hk}]{k}[/] {d}" for k, d in parts)
        try:
            self.query_one("#spell-hints", Static).update(text)
        except Exception:
            pass

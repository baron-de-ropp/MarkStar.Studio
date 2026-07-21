"""An Input that completes filesystem paths on Tab.

Type a few characters of a path and press Tab: the field fills in the longest
unambiguous completion. Press Tab again at a branch point to cycle through the
candidates. Directory completions get a trailing separator so the next Tab
descends into them. Completion logic is the pure ``complete_path`` in
domain/pathcomplete; the Tab-cycle state lives in ``CompletionCycler`` so
quick-open can borrow it for its literal-path mode.
"""

from __future__ import annotations

from textual import events
from textual.widgets import Input

from markstar.domain.pathcomplete import complete_path


class CompletionCycler:
    """Tab-completion state machine over ``complete_path``.

    Holds the candidate list between presses: the first Tab fills the shared
    prefix, later Tabs at a branch point cycle. ``advance`` returns the new field
    value, or None when there is nothing to change.
    """

    def __init__(self) -> None:
        self._matches: list[str] = []
        self._cycle_i = 0

    def reset(self) -> None:
        self._matches = []
        self._cycle_i = 0

    def advance(self, value: str) -> str | None:
        # Already mid-cycle (the field holds the current suggestion) → advance.
        if (
            self._matches
            and self._matches[self._cycle_i] == value
            and len(self._matches) > 1
        ):
            self._cycle_i = (self._cycle_i + 1) % len(self._matches)
            return self._matches[self._cycle_i]

        completion, matches = complete_path(value)
        if not matches:
            self._matches = []
            return None
        if completion != value:
            # Fill in the shared prefix; a later Tab (when nothing more is common)
            # will start cycling via the branch below.
            self._matches = []
            return completion
        if len(matches) > 1:
            # At a branch point with several candidates → begin cycling.
            self._matches = matches
            self._cycle_i = 0
            return matches[0]
        # A single exact match already fills the field — nothing to do.
        return None


class PathInput(Input):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cycler = CompletionCycler()

    def on_key(self, event: events.Key) -> None:
        # Intercept Tab before the focus system moves focus away.
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self._complete()

    def _complete(self) -> None:
        completed = self._cycler.advance(self.value)
        if completed is not None:
            self._apply(completed)

    def _apply(self, value: str) -> None:
        self.value = value
        self.cursor_position = len(value)

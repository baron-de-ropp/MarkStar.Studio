"""An Input that completes filesystem paths on Tab.

Type a few characters of a path and press Tab: the field fills in the longest
unambiguous completion. Press Tab again at a branch point to cycle through the
candidates. Directory completions get a trailing separator so the next Tab
descends into them. Completion logic is the pure ``complete_path`` in
domain/pathcomplete.
"""

from __future__ import annotations

from textual import events
from textual.widgets import Input

from markstar.domain.pathcomplete import complete_path


class PathInput(Input):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._matches: list[str] = []
        self._cycle_i = 0

    def on_key(self, event: events.Key) -> None:
        # Intercept Tab before the focus system moves focus away.
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self._complete()

    def _complete(self) -> None:
        value = self.value
        # Already mid-cycle (the field holds the current suggestion) → advance.
        if self._matches and self._matches[self._cycle_i] == value and len(
            self._matches
        ) > 1:
            self._cycle_i = (self._cycle_i + 1) % len(self._matches)
            self._apply(self._matches[self._cycle_i])
            return

        completion, matches = complete_path(value)
        if not matches:
            self._matches = []
            return
        if completion != value:
            # Fill in the shared prefix; a later Tab (when nothing more is common)
            # will start cycling via the branch below.
            self._apply(completion)
            self._matches = []
        elif len(matches) > 1:
            # At a branch point with several candidates → begin cycling.
            self._matches = matches
            self._cycle_i = 0
            self._apply(matches[0])
        # else: a single exact match already fills the field — nothing to do.

    def _apply(self, value: str) -> None:
        self.value = value
        self.cursor_position = len(value)

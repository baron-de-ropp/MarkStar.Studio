"""TabBar — the clickable tab ribbon.

Owns its own rendering (theme-colored chips) and click hit-testing, and reports
user intent by posting ``TabBar.Activated`` / ``TabBar.Closed`` messages. The app
handles those; it no longer builds chip markup or tracks click bounds itself.

Chip layout (plain columns): ``{LEAD}{name}{GAP}×{TAIL}`` i.e. LEAD leading
spaces, the filename, GAP (" • " when dirty, "   " when clean) up to the × close
hot-spot, then TAIL ("× │"). Because the render string and the hit-testing both
derive from these constants, the close-× hot-spot can't drift from what's drawn.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.message import Message
from textual.widgets import Static

from markstar.ui.themes import token

LEAD = 3   # "   " before the name
GAP = 3    # " {dirty-marker} " between the name and the ×
TAIL = 3   # "× │" region width after name+gap (×, space, │)


@dataclass
class TabInfo:
    name: str
    dirty: bool


class TabBar(Static):
    class Activated(Message):
        """A tab body was clicked — switch to it."""

        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    class Closed(Message):
        """A tab's × was clicked — close it."""

        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # (start, end, close_col, index) per chip, in content columns.
        self._bounds: list[tuple[int, int, int, int]] = []

    def set_tabs(self, tabs: list[TabInfo], active_index: int) -> None:
        """Render the chips for ``tabs`` and record click bounds."""
        dim = token(self.app, "rule")
        chips: list[str] = []
        bounds: list[tuple[int, int, int, int]] = []
        cursor = 0
        for i, tab in enumerate(tabs):
            nc = token(self.app, "tab-active" if i == active_index else "tab-inactive")
            mid = "•" if tab.dirty else " "
            chips.append(f"[{nc}]   {tab.name} {mid} [/][{dim}]×[/] [{dim}]│[/]")
            width = LEAD + len(tab.name) + GAP + TAIL
            close_col = cursor + LEAD + len(tab.name) + GAP
            bounds.append((cursor, cursor + width, close_col, i))
            cursor += width
        self._bounds = bounds
        self.update("".join(chips))

    def hit_test(self, x: int) -> tuple[str, int] | None:
        """Map a content column to ("close" | "activate", tab_index), or None."""
        for start, end, close_col, idx in self._bounds:
            if start <= x < end:
                return ("close" if x == close_col else "activate", idx)
        return None

    def on_click(self, event: events.Click) -> None:
        hit = self.hit_test(event.x)
        if hit is None:
            return
        kind, idx = hit
        self.post_message(self.Closed(idx) if kind == "close" else self.Activated(idx))

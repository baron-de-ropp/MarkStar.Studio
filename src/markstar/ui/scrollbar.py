"""A slimmer scrollbar look.

Textual draws the scrollbar thumb as a full-width reverse block — a chunky solid
bar. This renderer draws the vertical thumb as a thin glyph (a right one-eighth
block) hugging the edge instead, so it reads as a slender line rather than a
heavy block. The cell is still full height; only the glyph is narrower.

Installed process-wide via ``ScrollBar.renderer`` (see install()). Horizontal
scrollbars fall back to Textual's default rendering.
"""

from __future__ import annotations

from rich.segment import Segment, Segments
from rich.style import Style
from textual.color import Color
from textual.scrollbar import ScrollBar, ScrollBarRender

# Thin thumb glyphs. Vertical: a right one-eighth block hugging the right edge.
# Horizontal: the box-drawing light horizontal — a true 1px line that connects
# seamlessly across cells (thinner than the ▁ eighth-block, which is chunky
# because a cell is ~2x taller than wide).
_THUMB_V = "▕"
_THUMB_H = "─"


class ThinScrollBarRender(ScrollBarRender):
    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        # Defaults are placeholders — Textual always passes the resolved colors.
        back_color: Color = Color(85, 85, 85),
        bar_color: Color = Color(128, 128, 128),
    ) -> Segments:
        glyph = _THUMB_V if vertical else _THUMB_H
        cell_w = thickness if vertical else 1
        track_style = Style(bgcolor=back_color)
        track = Segment(" " * cell_w, track_style)

        def assemble(segments):
            if vertical:
                return Segments(segments, new_lines=True)
            # A single horizontal row (per thickness); Segment.line() ends it.
            return Segments((segments + [Segment.line()]) * thickness, new_lines=False)

        scrollable = window_size and size and virtual_size and size != virtual_size
        if not scrollable:
            return assemble([track] * int(size))

        thumb_size = max(1, round(window_size / (virtual_size / size)))
        span = max(0, virtual_size - window_size)
        ratio = (position / span) if span else 0.0
        start = round((size - thumb_size) * ratio)
        end = start + thumb_size

        thumb = Segment(
            glyph * cell_w,
            Style(color=bar_color, bgcolor=back_color, meta={"@mouse.down": "grab"}),
        )
        segments = [track] * int(size)
        for i in range(max(0, start), min(int(size), end)):
            segments[i] = thumb
        return assemble(segments)


def install() -> None:
    """Make the thin renderer the default for every scrollbar in the app."""
    ScrollBar.renderer = ThinScrollBarRender

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

# Right one-eighth block: a thin vertical line flush to the right edge, where the
# vertical scrollbar sits. Consecutive cells join into one continuous slim line.
_THUMB = "▕"


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
        if not vertical:
            return super().render_bar(
                size=size,
                virtual_size=virtual_size,
                window_size=window_size,
                position=position,
                thickness=thickness,
                vertical=vertical,
                back_color=back_color,
                bar_color=bar_color,
            )

        width = thickness
        track_style = Style(bgcolor=back_color)
        blank = " " * width
        track = Segment(blank, track_style)

        scrollable = (
            window_size and size and virtual_size and size != virtual_size
        )
        if not scrollable:
            return Segments([track] * int(size), new_lines=True)

        thumb_size = max(1, round(window_size / (virtual_size / size)))
        span = max(0, virtual_size - window_size)
        ratio = (position / span) if span else 0.0
        start = round((size - thumb_size) * ratio)
        end = start + thumb_size

        thumb = Segment(
            _THUMB * width,
            Style(color=bar_color, bgcolor=back_color, meta={"@mouse.down": "grab"}),
        )
        segments = [track] * int(size)
        for i in range(max(0, start), min(int(size), end)):
            segments[i] = thumb
        return Segments(segments, new_lines=True)


def install() -> None:
    """Make the thin renderer the default for every scrollbar in the app."""
    ScrollBar.renderer = ThinScrollBarRender

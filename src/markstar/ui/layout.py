"""Pure prose-layout geometry.

The math that positions the writing column (and the overlay panel's width) given
the terminal width. No widgets, no side effects — the app applies the result to
its widget tree in ``_update_prose_layout``. Kept separate so it's trivially
unit-testable (see tests/test_tabs.py::test_* layout cases).
"""

from __future__ import annotations

from typing import NamedTuple

# Side inset (left/right margin of the prose column) — wider on roomy windows,
# tighter on narrow ones, switching at the breakpoint.
SIDE_INSET_WIDE = 5
SIDE_INSET_NARROW = 2
NARROW_BREAKPOINT = 90       # window width at/above which the wide inset applies
MIN_PROSE_COLS = 24          # prose never shrinks below this behind the panel
MIN_PANEL_COLS = 15          # project-panel floor (mirrors the config clamp low bound)


class ProseLayout(NamedTuple):
    panel: int      # project-panel width (0 when closed) — overlay, not reserved
    left_pad: int   # columns left of the prose column
    col: int        # prose column width
    right_pad: int  # columns right of the prose column


def compute_layout(
    width: int,
    panel_open: bool,
    *,
    center_text: bool,
    prose_width: int,
    min_panel_width: int,
) -> ProseLayout:
    """Return the prose column geometry for a given terminal ``width``.

    The panel is an OVERLAY (its own layer): it floats on top of the prose and
    does NOT reserve width, so the prose column is always centered in the full
    window. On a window too narrow to clear it, the panel simply overlaps the
    text, which is acceptable. ``panel`` is clamped so the prose keeps at least
    ``MIN_PROSE_COLS`` columns when the panel is open.
    """
    panel = 0
    if panel_open:
        panel = max(MIN_PANEL_COLS, min(min_panel_width, width - MIN_PROSE_COLS))
        panel = max(0, panel)
    available = max(1, width)
    base = SIDE_INSET_WIDE if width >= NARROW_BREAKPOINT else SIDE_INSET_NARROW
    if center_text:
        col = min(prose_width, max(1, available - 2 * base))
        side = max(base, (available - col) // 2)
    else:
        side = base
        col = max(1, available - 2 * base)
    left_pad = side
    right_pad = max(0, width - left_pad - col)
    return ProseLayout(panel, left_pad, col, right_pad)

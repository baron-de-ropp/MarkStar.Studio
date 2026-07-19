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
PANEL_GAP = 5                # gap kept between the panel's right edge and the prose


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
    window. Its width fills the left margin — up to ``PANEL_GAP`` columns before
    the prose begins — but never narrower than ``min_panel_width``. On a window
    too narrow to fit both, it falls back to that minimum and overlaps the prose,
    which is acceptable.
    """
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

    panel = 0
    if panel_open:
        # Expand to fill the left margin, stopping PANEL_GAP columns short of the
        # prose; floor at the configured minimum (overlaps only when too narrow).
        panel = max(min_panel_width, left_pad - PANEL_GAP)
        panel = max(0, min(panel, width))
    return ProseLayout(panel, left_pad, col, right_pad)

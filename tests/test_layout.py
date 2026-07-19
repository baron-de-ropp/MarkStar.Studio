"""Pure prose-layout geometry (ui/layout.compute_layout)."""

from __future__ import annotations

from markstar.ui.layout import ProseLayout, compute_layout


def _layout(width, panel_open, *, center=True, prose=120, min_panel=40):
    return compute_layout(
        width,
        panel_open,
        center_text=center,
        prose_width=prose,
        min_panel_width=min_panel,
    )


def test_columns_always_tile_the_full_width() -> None:
    for width in (40, 50, 76, 100, 120, 160, 200):
        lay = _layout(width, panel_open=False)
        assert lay.left_pad + lay.col + lay.right_pad == width


def test_panel_is_overlay_and_does_not_shift_prose() -> None:
    for width in (50, 100, 160):
        closed = _layout(width, panel_open=False)
        opened = _layout(width, panel_open=True)
        assert closed.panel == 0 and opened.panel > 0
        # Opening the panel must not move the prose column.
        assert (opened.left_pad, opened.col, opened.right_pad) == (
            closed.left_pad,
            closed.col,
            closed.right_pad,
        )


def test_centering_caps_at_prose_width() -> None:
    lay = _layout(300, panel_open=False, center=True, prose=120)
    assert lay.col == 120
    assert lay.left_pad == lay.right_pad  # symmetric when centered


def test_uncentered_fills_available_minus_insets() -> None:
    lay = _layout(200, panel_open=False, center=False)
    assert lay.col == 200 - 2 * lay.left_pad


def test_panel_fills_left_margin_on_wide_window() -> None:
    # 300 wide, prose capped at 120 and centered → left_pad 90; the panel expands
    # to fill the margin, stopping PANEL_GAP (5) columns short of the prose.
    lay = _layout(300, panel_open=True, min_panel=40)
    assert lay.panel == lay.left_pad - 5


def test_panel_floors_at_min_when_margin_is_small() -> None:
    # 50 wide: the left margin is tiny, so the panel falls back to its minimum.
    lay = _layout(50, panel_open=True, min_panel=40)
    assert lay.panel == 40


def test_panel_never_exceeds_window_width() -> None:
    lay = _layout(30, panel_open=True, min_panel=40)
    assert lay.panel == 30  # capped at the terminal width (overlaps the prose)


def test_returns_named_tuple() -> None:
    lay = _layout(100, panel_open=False)
    assert isinstance(lay, ProseLayout)
    assert lay == (lay.panel, lay.left_pad, lay.col, lay.right_pad)

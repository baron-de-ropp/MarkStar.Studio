"""Pure prose-layout geometry (ui/layout.compute_layout)."""

from __future__ import annotations

from markstar.ui.layout import MIN_PROSE_COLS, ProseLayout, compute_layout


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


def test_panel_clamped_to_keep_min_prose() -> None:
    # Very narrow window: panel can't eat below MIN_PROSE_COLS of prose room.
    lay = _layout(30, panel_open=True, min_panel=40)
    assert lay.panel <= 30 - MIN_PROSE_COLS


def test_returns_named_tuple() -> None:
    lay = _layout(100, panel_open=False)
    assert isinstance(lay, ProseLayout)
    assert lay == (lay.panel, lay.left_pad, lay.col, lay.right_pad)

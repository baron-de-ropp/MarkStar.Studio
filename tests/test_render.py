"""Inline Markdown rendering (style spans) and theme token resolution."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp, MarkStarTextArea, _markdown_spans
from markstar.ui.themes import token


def _run(coro):
    return asyncio.run(coro)


def test_markdown_spans_bold_marks_and_content() -> None:
    spans = _markdown_spans("a **bold** c")
    # marker(2,4) strong(4,8) marker(8,10)
    assert (2, 4, "marker") in spans
    assert (4, 8, "strong") in spans
    assert (8, 10, "marker") in spans


def test_markdown_spans_heading() -> None:
    spans = _markdown_spans("## Title")
    assert spans[0] == (0, 3, "marker")
    assert spans[1] == (3, len("## Title"), "heading")


def test_italic_not_matched_inside_bold() -> None:
    # The ** markers must not be picked up as italic single-*.
    spans = _markdown_spans("**x**")
    assert not any(kind == "emphasis" for _, _, kind in spans)


def test_get_line_applies_bold_style() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("a **bold** c")
            await pilot.pause()
            line = ed.get_line(0)
            return any(s.style.bold for s in line.spans)

    assert _run(go()) is True


def test_toggle_formatting_off_removes_styling() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("a **bold** c")
            await pilot.pause()
            ed.set_render_markdown(False)
            await pilot.pause()
            line = ed.get_line(0)
            return any(s.style.bold for s in line.spans)

    assert _run(go()) is False


def test_blockquote_spans() -> None:
    spans = _markdown_spans("> quoted")
    assert spans[0] == (0, 2, "marker")
    assert spans[1] == (2, len("> quoted"), "quote")


def test_fenced_code_block_line_map() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("pre\n```\nx = 1\n```\npost")
            await pilot.pause()
            return dict(ed._fence_lines)

    fences = _run(go())
    assert fences.get(1) == "fence"   # opening ```
    assert fences.get(2) == "code"    # x = 1
    assert fences.get(3) == "fence"   # closing ```
    assert 0 not in fences and 4 not in fences  # pre / post untouched


def test_bullet_and_numbered_list_markers() -> None:
    assert (0, 2, "marker") in _markdown_spans("- item")
    assert (0, 2, "marker") in _markdown_spans("+ item")
    assert (0, 3, "marker") in _markdown_spans("1. item")


def test_star_bullet_is_list_not_italic() -> None:
    spans = _markdown_spans("* a bullet")
    assert (0, 2, "marker") in spans
    assert not any(kind == "emphasis" for _, _, kind in spans)


def test_link_spans() -> None:
    spans = _markdown_spans("[text](https://x.com)")
    assert any(kind == "link" for _, _, kind in spans)
    assert sum(1 for _, _, kind in spans if kind == "marker") >= 2


def test_theme_cycle_changes_tokens() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            before = app.theme
            marker_before = token(app, "md-marker")
            app.cmd_cycle_theme()
            await pilot.pause()
            return before, app.theme, marker_before, token(app, "md-marker")

    b, a, mb, ma = _run(go())
    assert a != b
    assert mb != ma

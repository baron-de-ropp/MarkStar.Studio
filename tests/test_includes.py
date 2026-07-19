"""Include compilation: expansion, nesting, missing files, cycles + editor token."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp, MarkStarTextArea, _markdown_spans
from markstar.domain.includes import compile_document, make_resolver


def _run(coro):
    return asyncio.run(coro)


def _project(tmp_path):
    (tmp_path / "main.md").write_text("# Book\n\n![[chapter-01]]\n\n![[chapter-02]]\n")
    (tmp_path / "chapter-01.md").write_text("## One\n![[shared]]")
    (tmp_path / "chapter-02.md").write_text("## Two")
    (tmp_path / "shared.md").write_text("(shared)")
    return tmp_path


def test_expands_nested_includes(tmp_path) -> None:
    d = _project(tmp_path)
    resolve = make_resolver(d)
    out, errors = compile_document(
        (d / "main.md").read_text(), d, resolve, self_path=d / "main.md"
    )
    assert "## One" in out and "## Two" in out and "(shared)" in out
    assert "![[" not in out
    assert errors == []


def test_missing_include_reports_and_marks(tmp_path) -> None:
    resolve = make_resolver(tmp_path)
    out, errors = compile_document("a ![[nope]] b", tmp_path, resolve)
    assert any("missing" in e for e in errors)
    assert "missing include: nope" in out


def test_cycle_detected(tmp_path) -> None:
    (tmp_path / "a.md").write_text("A ![[b]]")
    (tmp_path / "b.md").write_text("B ![[a]]")
    resolve = make_resolver(tmp_path)
    out, errors = compile_document(
        (tmp_path / "a.md").read_text(), tmp_path, resolve, self_path=tmp_path / "a.md"
    )
    assert any("cycle" in e for e in errors)


def test_resolver_prefers_file_dir_then_project_root(tmp_path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "note.md").write_text("local")
    (tmp_path / "note.md").write_text("root-level")
    resolve = make_resolver(tmp_path)
    # From inside sub/, "note" resolves to sub/note.md first.
    assert resolve("note", tmp_path / "sub").read_text() == "local"
    # From the top, it resolves to the top-level note.md.
    assert resolve("note", tmp_path).read_text() == "root-level"


def test_include_token_rendered_in_editor(tmp_path) -> None:
    # Pure span detection
    spans = _markdown_spans("see ![[chapter-01]] here")
    assert any(kind == "include" for _, _, kind in spans)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("intro ![[part-two]] end")
            await pilot.pause()
            line = ed.get_line(0)
            # the include token gets a bold style span
            return any(s.style.bold for s in line.spans)

    assert _run(go()) is True


def test_compile_command_writes_expanded_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    d = _project(tmp_path)
    out_file = d / "book.compiled.md"

    async def go():
        from unittest.mock import AsyncMock, patch

        app = MarkStarApp(path=d / "main.md")
        async with app.run_test() as pilot:
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value=str(out_file))
            ):
                await app._compile_async()
            await pilot.pause()

    _run(go())
    text = out_file.read_text()
    assert "## One" in text and "## Two" in text and "![[" not in text

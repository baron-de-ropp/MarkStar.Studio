"""ProjectTools: list/grep/read, path-escape safety, dispatch."""

from __future__ import annotations

from markstar.ai.tools import ProjectTools


def _project(tmp_path):
    (tmp_path / "book").mkdir()
    (tmp_path / "book" / "ch-01.md").write_text("The sigil glowed blue.\nKael waited.")
    (tmp_path / "book" / "ch-02.md").write_text("The sigil glowed silver here.")
    (tmp_path / "series.md").write_text("Sigils are silver.")
    (tmp_path / "cover.png").write_bytes(b"\x89PNG")
    (tmp_path / ".hidden.md").write_text("secret")
    return ProjectTools(tmp_path)


def test_list_files_shows_project_and_skips_hidden(tmp_path) -> None:
    out = _project(tmp_path).list_files()
    assert "book/ch-01.md" in out and "series.md" in out and "cover.png" in out
    assert ".hidden.md" not in out


def test_grep_finds_matches_with_locations(tmp_path) -> None:
    out = _project(tmp_path).grep("sigil")
    assert "book/ch-01.md:1:" in out
    assert "book/ch-02.md:1:" in out
    # png is binary/non-text → not searched
    assert "cover.png" not in out


def test_grep_invalid_regex_is_reported(tmp_path) -> None:
    assert "invalid regex" in _project(tmp_path).grep("(")


def test_read_file_returns_numbered_lines(tmp_path) -> None:
    out = _project(tmp_path).read_file("book/ch-01.md")
    assert "1  The sigil glowed blue." in out
    assert "2  Kael waited." in out


def test_read_file_rejects_path_escape(tmp_path) -> None:
    tools = _project(tmp_path)
    assert "no such file" in tools.read_file("../../etc/passwd")
    assert "no such file" in tools.read_file("/etc/passwd")


def test_execute_dispatches_by_name(tmp_path) -> None:
    tools = _project(tmp_path)
    assert "series.md" in tools.execute("list_files", "{}")
    assert "book/ch-02.md" in tools.execute("grep", '{"pattern": "silver"}')
    assert "Kael" in tools.execute("read_file", '{"path": "book/ch-01.md"}')
    assert "unknown tool" in tools.execute("nope", "{}")


def test_execute_tolerates_bad_json(tmp_path) -> None:
    # Should not raise; falls back to empty args.
    out = _project(tmp_path).execute("list_files", "{not json")
    assert "series.md" in out


def test_summarize_call_is_short() -> None:
    assert ProjectTools.summarize_call("grep", '{"pattern":"x"}') == 'grep "x"'
    assert ProjectTools.summarize_call("read_file", '{"path":"a.md"}') == "read a.md"
    assert ProjectTools.summarize_call("list_files", "{}") == "list files"

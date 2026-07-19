"""Pure filesystem path completion (domain/pathcomplete.complete_path)."""

from __future__ import annotations

import os

from markstar.domain.pathcomplete import complete_path


def _make(tmp_path):
    (tmp_path / "chapters").mkdir()
    (tmp_path / "characters").mkdir()
    (tmp_path / "chapter-notes.md").write_text("x")
    (tmp_path / "README.md").write_text("x")
    (tmp_path / ".hidden").write_text("x")
    return tmp_path


def test_common_prefix_across_candidates(tmp_path) -> None:
    _make(tmp_path)
    completion, matches = complete_path(str(tmp_path / "ch"))
    assert completion == str(tmp_path / "cha")  # chapter*/character* share "cha"
    names = sorted(os.path.basename(m.rstrip(os.sep)) for m in matches)
    assert names == ["chapter-notes.md", "chapters", "characters"]


def test_single_directory_gets_trailing_separator(tmp_path) -> None:
    _make(tmp_path)
    completion, matches = complete_path(str(tmp_path / "characters"))
    assert len(matches) == 1
    assert completion.endswith(os.sep)


def test_single_file_completes_fully(tmp_path) -> None:
    _make(tmp_path)
    completion, matches = complete_path(str(tmp_path / "READ"))
    assert len(matches) == 1
    assert completion == str(tmp_path / "README.md")


def test_trailing_separator_lists_directory(tmp_path) -> None:
    _make(tmp_path)
    _completion, matches = complete_path(str(tmp_path) + os.sep)
    # Lists everything except the dotfile (hidden unless explicitly typed).
    names = {os.path.basename(m.rstrip(os.sep)) for m in matches}
    assert names == {"chapters", "characters", "chapter-notes.md", "README.md"}


def test_hidden_only_shows_when_dot_typed(tmp_path) -> None:
    _make(tmp_path)
    # Build the string literally — Path() would collapse a trailing ".".
    _c, matches = complete_path(str(tmp_path) + os.sep + ".")
    assert [os.path.basename(m) for m in matches] == [".hidden"]


def test_no_match_returns_input_unchanged(tmp_path) -> None:
    _make(tmp_path)
    text = str(tmp_path / "zzz")
    assert complete_path(text) == (text, [])


def test_nonexistent_directory_is_safe(tmp_path) -> None:
    text = str(tmp_path / "nope" / "deeper")
    assert complete_path(text) == (text, [])

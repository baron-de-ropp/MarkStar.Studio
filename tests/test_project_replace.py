"""Project-wide replace across on-disk documents."""

from __future__ import annotations

from pathlib import Path

from markstar.domain.projectsearch import replace_in_project, search_project


def _project(root: Path) -> None:
    (root / "ch1.md").write_text("The warden sleeps.\n", encoding="utf-8")
    (root / "ch2.md").write_text("nothing here\n", encoding="utf-8")
    sub = root / "notes"
    sub.mkdir()
    (sub / "ideas.md").write_text("the Warden again\n", encoding="utf-8")


def test_replace_rewrites_every_matching_file(tmp_path: Path) -> None:
    _project(tmp_path)
    result = replace_in_project(tmp_path, "warden", "keeper", case_sensitive=False)
    assert result.replacements == 2
    assert result.files_changed == 2
    assert (tmp_path / "ch1.md").read_text(encoding="utf-8") == "The keeper sleeps.\n"
    assert (tmp_path / "notes" / "ideas.md").read_text(encoding="utf-8") == "the keeper again\n"
    assert (tmp_path / "ch2.md").read_text(encoding="utf-8") == "nothing here\n"


def test_replace_case_sensitive(tmp_path: Path) -> None:
    _project(tmp_path)
    result = replace_in_project(tmp_path, "Warden", "Keeper", case_sensitive=True)
    assert result.replacements == 1
    assert "Warden" not in (tmp_path / "notes" / "ideas.md").read_text(encoding="utf-8")
    assert "warden" in (tmp_path / "ch1.md").read_text(encoding="utf-8")


def test_replace_empty_query_is_noop(tmp_path: Path) -> None:
    _project(tmp_path)
    before = (tmp_path / "ch1.md").read_text(encoding="utf-8")
    result = replace_in_project(tmp_path, "", "x")
    assert result.replacements == 0
    assert result.files_changed == 0
    assert (tmp_path / "ch1.md").read_text(encoding="utf-8") == before


def test_replace_counts_match_search(tmp_path: Path) -> None:
    _project(tmp_path)
    hits = len(search_project(tmp_path, "warden").hits)
    result = replace_in_project(tmp_path, "warden", "X", case_sensitive=False)
    assert result.replacements == hits

"""Project-wide find: every hit, bounded, and honest when it stops early."""

from __future__ import annotations

from pathlib import Path

from markstar.domain.projectsearch import search_project


def _project(root: Path) -> None:
    (root / "ch1.md").write_text("The warden sleeps.\nA torch burns.\n", encoding="utf-8")
    (root / "ch2.md").write_text("nothing here\n", encoding="utf-8")
    sub = root / "notes"
    sub.mkdir()
    (sub / "ideas.md").write_text("x\ny\nthe Warden again\n", encoding="utf-8")
    (root / "cover.png").write_bytes(b"\x89PNG")


def test_finds_hits_across_files(tmp_path: Path) -> None:
    _project(tmp_path)
    r = search_project(tmp_path, "warden")
    assert [(h.relative, h.line) for h in r.hits] == [("ch1.md", 0), ("notes/ideas.md", 2)]


def test_line_and_column_are_correct(tmp_path: Path) -> None:
    _project(tmp_path)
    hit = search_project(tmp_path, "torch").hits[0]
    assert (hit.line, hit.column) == (1, 2)  # "A torch burns."


def test_preview_is_the_matching_line(tmp_path: Path) -> None:
    _project(tmp_path)
    assert search_project(tmp_path, "torch").hits[0].preview == "A torch burns."


def test_case_sensitivity_is_honoured(tmp_path: Path) -> None:
    _project(tmp_path)
    assert len(search_project(tmp_path, "Warden", case_sensitive=True).hits) == 1
    assert len(search_project(tmp_path, "warden", case_sensitive=False).hits) == 2


def test_non_documents_are_not_searched(tmp_path: Path) -> None:
    _project(tmp_path)
    assert search_project(tmp_path, "PNG").hits == []


def test_empty_query_finds_nothing(tmp_path: Path) -> None:
    _project(tmp_path)
    assert search_project(tmp_path, "").hits == []


def test_truncation_is_reported(tmp_path: Path) -> None:
    (tmp_path / "big.md").write_text("hit\n" * 50, encoding="utf-8")
    r = search_project(tmp_path, "hit", max_hits=10)
    assert len(r.hits) == 10
    assert r.truncated is True  # never pretend the list was complete


def test_untruncated_results_say_so(tmp_path: Path) -> None:
    _project(tmp_path)
    assert search_project(tmp_path, "warden").truncated is False

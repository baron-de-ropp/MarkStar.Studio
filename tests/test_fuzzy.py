"""Fuzzy quick-open scoring: does typing a fragment surface the right file?"""

from __future__ import annotations

from markstar.domain.fuzzy import fuzzy_score, rank


def test_non_subsequence_does_not_match() -> None:
    assert fuzzy_score("zzz", "chapter.md") is None


def test_subsequence_matches_with_gaps() -> None:
    assert fuzzy_score("ch3", "chapter-3.md") is not None


def test_match_is_case_insensitive() -> None:
    assert fuzzy_score("CH", "chapter.md") is not None


def test_empty_query_matches_everything_at_zero() -> None:
    assert fuzzy_score("", "anything.md") == 0


def test_filename_hit_beats_folder_hit() -> None:
    """'chap' should mean the file called chap-something, not a chap/ folder."""
    in_name = fuzzy_score("chap", "notes/chapter.md")
    in_folder = fuzzy_score("chap", "chapel/unrelated.md")
    assert in_name > in_folder


def test_consecutive_run_beats_scattered_letters() -> None:
    run = fuzzy_score("chap", "chapter.md")
    scattered = fuzzy_score("chap", "cottage-harp.md")
    assert run > scattered


def test_shorter_path_wins_all_else_equal() -> None:
    short = fuzzy_score("ch", "ch.md")
    long = fuzzy_score("ch", "a/very/deeply/nested/folder/tree/ch.md")
    assert short > long


def test_rank_orders_best_first() -> None:
    out = rank("ch3", ["notes.md", "chapter-3.md", "misc/c-h-3.md"])
    assert out[0] == "chapter-3.md"
    assert "notes.md" not in out  # no subsequence match


def test_rank_floats_recents_above_equal_matches() -> None:
    candidates = ["draft/chapter.md", "chapter.md"]
    out = rank("chapter", candidates, boost={"draft/chapter.md"})
    assert out[0] == "draft/chapter.md"


def test_rank_preserves_incoming_order_for_empty_query() -> None:
    candidates = ["b.md", "a.md", "c.md"]
    assert rank("", candidates) == candidates


def test_rank_respects_limit() -> None:
    assert len(rank("a", [f"a{i}.md" for i in range(50)], limit=5)) == 5

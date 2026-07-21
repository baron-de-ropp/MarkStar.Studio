"""Markdown outline: the document's own headings are its table of contents."""

from __future__ import annotations

from markstar.domain.outline import headings


def test_levels_and_lines() -> None:
    md = "# Book\n\n## Chapter\n\ntext\n\n### Scene\n"
    assert headings(md) == [(1, "Book", 0), (2, "Chapter", 2), (3, "Scene", 6)]


def test_headings_inside_code_fences_are_ignored() -> None:
    md = "# Real\n\n```sh\n# not a heading\n## also not\n```\n\n## Also real\n"
    assert [h.text for h in headings(md)] == ["Real", "Also real"]


def test_tilde_fences_too() -> None:
    md = "# Real\n~~~\n# hidden\n~~~\n"
    assert [h.text for h in headings(md)] == ["Real"]


def test_closing_hashes_are_stripped() -> None:
    assert headings("## The Vault ##")[0].text == "The Vault"


def test_empty_heading_is_labelled() -> None:
    assert headings("## \n")[0].text == "(untitled)"


def test_no_headings() -> None:
    assert headings("just prose\n\nmore prose") == []


def test_hash_without_space_is_not_a_heading() -> None:
    assert headings("#tag not a heading") == []

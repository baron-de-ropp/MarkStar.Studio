"""Prose word counting: markup must not inflate a manuscript's word count."""

from __future__ import annotations

from markstar.domain.wordcount import count, prose_text


def test_plain_prose_is_unchanged() -> None:
    assert count("The warden sleeps.").words == 3


def test_emphasis_markers_are_not_words_or_characters() -> None:
    plain = count("The warden sleeps.")
    marked = count("The **warden** *sleeps*.")
    assert marked == plain


def test_underscore_emphasis_too() -> None:
    assert count("The __warden__ _sleeps_.") == count("The warden sleeps.")


def test_heading_keeps_its_words_but_not_its_hashes() -> None:
    c = count("## The Sunless Vault")
    assert c.words == 3
    assert "#" not in prose_text("## The Sunless Vault")


def test_fenced_code_is_excluded() -> None:
    md = "Prose here.\n\n```python\nx = 1\nprint(x)\n```\n\nMore prose."
    assert count(md).words == 4  # "Prose here." + "More prose."


def test_tilde_fence_is_excluded() -> None:
    md = "Before.\n~~~\nnot prose at all\n~~~\nAfter."
    assert count(md).words == 2


def test_inline_code_is_excluded() -> None:
    assert count("Set the `dungeon_level` variable.").words == 3


def test_link_text_counts_but_url_does_not() -> None:
    c = count("See [the warden](https://example.com/very/long/path).")
    assert c.words == 3  # "See the warden." — the URL contributes nothing
    assert "example.com" not in prose_text("See [the warden](https://example.com).")


def test_image_alt_text_counts_not_the_path() -> None:
    assert "cover.png" not in prose_text("![a grim cover](art/cover.png)")


def test_include_tokens_are_excluded() -> None:
    assert count("![[chapter-3]]").words == 0


def test_html_comments_are_excluded() -> None:
    assert count("Real prose. <!-- TODO: fix this later -->").words == 2


def test_multiline_html_comment_is_excluded() -> None:
    assert count("Keep.\n<!--\ndrop\nall\nthis\n-->\nKeep.").words == 2


def test_list_markers_are_not_words() -> None:
    assert count("- sword\n- shield\n- torch").words == 3


def test_numbered_list_markers_are_not_words() -> None:
    assert count("1. sword\n2. shield").words == 2


def test_blockquote_markers_are_not_words() -> None:
    assert count("> The vault is sealed.").words == 4


def test_horizontal_rule_is_not_a_word() -> None:
    assert count("Before.\n\n---\n\nAfter.").words == 2


def test_bullet_list_is_not_mistaken_for_italics() -> None:
    """'* item' is a list marker; '*item*' is emphasis. Both must count as 1."""
    assert count("* sword").words == 1
    assert count("*sword*").words == 1


def test_empty_document() -> None:
    assert count("") == (0, 0)


def test_realistic_supplement_page() -> None:
    md = (
        "# Room 2: The Flooded Hall\n\n"
        "The water is **waist-deep** and *cold*.\n"
        "See [the warden](monsters.md#warden).\n\n"
        "- a rusted key\n"
        "- ~~a torch~~\n\n"
        "<!-- check this against the map -->\n"
        "```\nstat block goes here\n```\n"
    )
    c = count(md)
    # Room 2: The Flooded Hall (5) + The water is waist-deep and cold. (6)
    # + See the warden. (3) + a rusted key (3) + a torch (2) = 19
    assert c.words == 19

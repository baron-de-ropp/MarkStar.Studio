"""Spellcheck domain: the pure misspelling finder + the Speller wrapper."""

from __future__ import annotations

from markstar.domain.spellcheck import Speller, find_misspellings


def _known(vocab):
    v = {w.lower() for w in vocab}
    return lambda w: w.lower() in v


def _words(text, known):
    return [text[m.start : m.end] for m in find_misspellings(text, known)]


def test_flags_only_unknown_words() -> None:
    known = _known({"the", "brown", "fox", "is", "here"})
    assert _words("the quikc brown fox", known) == ["quikc"]


def test_skips_inline_code_and_fences() -> None:
    known = _known({"use", "this"})
    assert _words("use `zzxx` this", known) == []
    assert _words("```\nzzxx qqww\n```", known) == []


def test_skips_urls_and_short_and_digit_words() -> None:
    known = _known({"see", "now", "ok"})
    assert _words("see https://zzxx.example.com now", known) == []
    assert _words("ok a b2 x9y", known) == []


def test_offsets_are_document_absolute() -> None:
    known = _known({"line", "one", "two"})
    text = "line one\nline zzxx two"
    matches = find_misspellings(text, known)
    assert len(matches) == 1
    m = matches[0]
    assert text[m.start : m.end] == "zzxx"


def test_speller_flags_and_suggests() -> None:
    sp = Speller()
    sp.prime()
    assert sp.known("hello") is True
    assert sp.known("teh") is False
    assert "the" in sp.suggestions("teh")


def test_speller_personal_dictionary_and_ignore() -> None:
    sp = Speller()
    sp.prime()
    assert sp.known("markstar") is False
    sp.add("markstar")
    assert sp.known("markstar") is True
    assert "markstar" in sp.added_words

    sp.ignore("zzqqxx")
    assert sp.known("zzqqxx") is True
    assert "zzqqxx" not in sp.added_words  # ignore is session-only, not saved

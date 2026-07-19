"""SpellController driven with stubs — walk-through + toggle, no app/UI needed."""

from __future__ import annotations

from markstar.config import Preferences
from markstar.domain.document import Document
from markstar.ui.spell_controller import SpellController


class _Bar:
    def __init__(self):
        self.shown = None
        self.is_visible = False
        self.hidden = False

    def show_word(self, word, suggestions, i, total):
        self.shown = (word, i, total)
        self.is_visible = True

    def hide(self):
        self.hidden = True
        self.is_visible = False


class _Editor:
    def __init__(self):
        self.highlights = None
        self.focused = False

    def set_spell_highlights(self, matches):
        self.highlights = matches

    def clear_spell_highlights(self):
        self.highlights = []

    def focus(self):
        self.focused = True


def _make(text="the helo wrld", **prefs_kwargs):
    prefs = Preferences(spellcheck=True, **prefs_kwargs)
    editor, bar, doc = _Editor(), _Bar(), Document(text=text)
    selections: list[tuple[int, int]] = []
    notes: list[tuple] = []
    _noop = lambda *a, **k: None  # noqa: E731
    sc = SpellController(
        prefs=prefs,
        get_editor=lambda: editor,
        get_bar=lambda: bar,
        get_document=lambda: doc,
        select_range=lambda a, b: selections.append((a, b)),
        notify=lambda *a, **k: notes.append(a),
        set_timer=_noop,
        run_worker=_noop,
        call_from_thread=_noop,
        push_screen_wait=_noop,
        screen_size=_noop,
    )
    sc.speller.prime()
    return sc, prefs, doc, editor, bar, selections, notes


def test_toggle_flips_and_persists() -> None:
    sc, prefs, *_ = _make()
    assert sc.enabled is True
    sc.toggle()
    assert sc.enabled is False and prefs.spellcheck is False
    sc.toggle()
    assert sc.enabled is True and prefs.spellcheck is True


def test_start_walk_parks_on_first_misspelling() -> None:
    sc, prefs, doc, editor, bar, selections, notes = _make()
    sc.start_walk()
    assert sc.current is not None
    assert sc.current[2] == "helo"  # first misspelled word
    assert bar.shown == ("helo", 1, 2)
    assert selections  # its range was selected


def test_add_puts_word_in_dictionary_and_advances() -> None:
    sc, prefs, doc, editor, bar, selections, notes = _make()
    sc.start_walk()  # on "helo"
    sc.on_request("add", "")
    assert sc.speller.known("helo")
    assert "helo" in prefs.spell_added  # persisted
    assert sc.current is not None and sc.current[2] == "wrld"  # advanced


def test_skip_ignores_for_session_only_and_advances() -> None:
    sc, prefs, doc, editor, bar, selections, notes = _make()
    sc.start_walk()  # on "helo"
    sc.on_request("skip", "")
    assert sc.speller.known("helo")  # ignored → treated as known
    assert "helo" not in prefs.spell_added  # but not persisted
    assert sc.current is not None and sc.current[2] == "wrld"


def test_walk_completes_when_no_more_misspellings() -> None:
    sc, prefs, doc, editor, bar, selections, notes = _make(text="hello world")
    sc.start_walk()
    assert sc.current is None  # both words are correct
    assert any("No misspellings" in str(n) for n in notes)

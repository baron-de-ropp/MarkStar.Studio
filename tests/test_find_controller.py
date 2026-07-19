"""FindController driven with stubs — no app/UI needed (the extraction payoff)."""

from __future__ import annotations

from markstar.domain.document import Document
from markstar.ui.find_controller import FindController


class _StubBar:
    def __init__(self, query="", replacement="", visible=True, replace=True):
        self.query = query
        self.replacement = replacement
        self.is_visible = visible
        self.is_replace_mode = replace
        self.count = None  # (current, total)

    def set_match_count(self, current, total):
        self.count = (current, total)

    def show(self, **kwargs):
        self.is_visible = True

    def expand_replace(self):
        self.is_replace_mode = True


class _StubEditor:
    def __init__(self):
        self.selected_text = ""
        self.highlights = None

    def set_search_highlights(self, matches):
        self.highlights = matches

    def clear_search_highlights(self):
        self.highlights = []


def _make(text, *, query="", replacement=""):
    doc = Document(text=text)
    bar = _StubBar(query=query, replacement=replacement)
    editor = _StubEditor()
    selections: list[tuple[int, int]] = []
    notes: list[tuple] = []
    events = {"push": 0, "refresh": 0}
    fc = FindController(
        get_editor=lambda: editor,
        get_bar=lambda: bar,
        get_document=lambda: doc,
        cursor_index=lambda: 0,
        select_range=lambda a, b: selections.append((a, b)),
        selection_start_index=lambda: None,
        notify=lambda *a, **k: notes.append((a, k)),
        push_editor=lambda: events.__setitem__("push", events["push"] + 1),
        refresh_status=lambda: events.__setitem__("refresh", events["refresh"] + 1),
    )
    return fc, doc, bar, editor, selections, notes, events


def test_find_next_selects_match_and_sets_count() -> None:
    fc, doc, bar, editor, selections, notes, events = _make(
        "cat sat on a cat mat", query="cat"
    )
    fc.find("next")
    assert selections[-1] == (0, 3)  # first "cat"
    assert bar.count == (1, 2)  # 1 of 2


def test_find_with_empty_query_warns() -> None:
    fc, doc, bar, editor, selections, notes, events = _make("text", query="")
    fc.find("next")
    assert notes and "Enter a find string" in notes[-1][0][0]


def test_replace_all_rewrites_document_and_notifies() -> None:
    fc, doc, bar, editor, selections, notes, events = _make(
        "cat cat cat", query="cat", replacement="dog"
    )
    fc.replace_all()
    assert doc.text == "dog dog dog"
    assert events["push"] == 1
    assert any("Replaced 3" in n[0][0] for n in notes)


def test_replace_one_replaces_and_advances() -> None:
    fc, doc, bar, editor, selections, notes, events = _make(
        "cat cat", query="cat", replacement="dog"
    )
    fc.replace_one()
    assert doc.text == "dog cat"  # first only
    assert selections[-1] == (4, 7)  # advanced to the next "cat"


def test_reset_clears_last_match_state() -> None:
    fc, doc, bar, editor, selections, notes, events = _make("cat cat", query="cat")
    fc.find("next")
    fc.reset()
    # After reset the count anchors on the cursor again, not the stale last-end.
    fc.update_count()
    assert bar.count == (1, 2)


def test_update_count_zero_matches() -> None:
    fc, doc, bar, editor, selections, notes, events = _make("nothing here", query="zzz")
    fc.update_count()
    assert bar.count == (None, 0)
    assert editor.highlights == []

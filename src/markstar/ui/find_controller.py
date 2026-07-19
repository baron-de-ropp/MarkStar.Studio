"""FindController — owns Find/Replace search state and coordination.

Previously this logic lived in MarkStarApp as a scatter of cmd_/_find_* methods
plus a bare ``_last_find_end`` instance attribute, tangled together with the
editor, the FindBar widget, the Document, and the pure search functions in
domain/search. This controller pulls the *coordination* into one cohesive place
while the pure matching/replacing stays in domain/search.

It reaches the widgets and a few editor helpers through injected callables (not a
direct app reference), so there's no circular import with app.py and it can be
driven with stubs in tests.
"""

from __future__ import annotations

from typing import Callable, Optional

from markstar.domain.search import (
    Match,
    find_all,
    find_next,
    replace_all,
    replace_match,
    step_find,
)


class FindController:
    def __init__(
        self,
        *,
        get_editor: Callable[[], object],
        get_bar: Callable[[], object],
        get_document: Callable[[], object],
        cursor_index: Callable[[], int],
        select_range: Callable[[int, int], None],
        selection_start_index: Callable[[], Optional[int]],
        notify: Callable[..., None],
        push_editor: Callable[[], None],
        refresh_status: Callable[[], None],
    ) -> None:
        self._editor = get_editor
        self._bar = get_bar
        self._document = get_document
        self._cursor_index = cursor_index
        self._select_range = select_range
        self._selection_start_index = selection_start_index
        self._notify = notify
        self._push_editor = push_editor
        self._refresh_status = refresh_status
        # End offset of the most recently focused match — the origin for stepping
        # to the next/previous occurrence and for the n/total badge.
        self._last_end = 0

    # --- state -------------------------------------------------------------

    def reset(self) -> None:
        """Forget the last-focused match (on tab switch, open, close, edit)."""
        self._last_end = 0

    # --- open / expand -----------------------------------------------------

    def open(self, *, replace: bool) -> None:
        """Show the find (or replace) bar; seed from a single-line selection.

        If the bar is already open and replace is requested, expand in place
        without wiping the find string.
        """
        bar = self._bar()
        if bar.is_visible:
            if replace:
                if not bar.is_replace_mode:
                    bar.expand_replace()
                else:
                    bar.query_one("#replace-input").focus()
                if bar.query:
                    self.update_count()
                return
            bar.query_one("#find-input").focus()
            return

        seed: str | None = None
        try:
            selected = self._editor().selected_text
        except Exception:
            selected = ""
        if selected and "\n" not in selected and len(selected) < 200:
            seed = selected
        bar.show(replace=replace, seed=seed)
        if bar.query:
            # Jump to the first match from the caret without requiring Enter.
            self.find("next", announce_missing=False)
            self.update_count()

    def on_expand(self) -> None:
        """The FindBar just expanded to replace mode — keep the count in sync."""
        bar = self._bar()
        if bar.query:
            self.update_count()

    def on_query_changed(self, query: str) -> None:
        self._last_end = 0
        self.update_count()
        if query:
            self.find("next", announce_missing=False)
        else:
            self.refresh_highlights()

    # --- stepping ----------------------------------------------------------

    def find(self, direction: str, *, announce_missing: bool = True) -> None:
        bar = self._bar()
        query = bar.query
        if not query:
            if announce_missing:
                self._notify("Enter a find string", severity="warning")
            if not bar.is_visible:
                bar.show(replace=False)
            return

        text = self._document().text
        cursor = self._cursor_index()

        # Prefer the start of the currently selected match as the step origin.
        current_start: int | None = None
        try:
            selected = self._editor().selected_text
        except Exception:
            selected = ""
        if selected and selected.lower() == query.lower():
            current_start = self._selection_start_index()
        if current_start is None and self._last_end:
            current_start = max(0, self._last_end - len(query))

        match = step_find(
            text, query, direction=direction, cursor=cursor, current_start=current_start
        )
        if match is None:
            if announce_missing:
                self._notify(f"Not found: {query!r}", severity="warning")
            self.update_count()
            return
        self._last_end = match.end
        self._select_range(match.start, match.end)
        self.update_count()

    # --- replace -----------------------------------------------------------

    def replace_one(self) -> None:
        bar = self._bar()
        if not bar.is_visible or not bar.is_replace_mode:
            self.open(replace=True)
            return
        query = bar.query
        if not query:
            self._notify("Enter a find string", severity="warning")
            return
        doc = self._document()
        cursor = self._cursor_index()
        try:
            selected = self._editor().selected_text
        except Exception:
            selected = ""
        match: Match | None = None
        if selected and selected.lower() == query.lower():
            start = self._selection_start_index()
            if start is not None:
                match = Match(start, start + len(selected))
        if match is None:
            match = find_next(doc.text, query, start=cursor)
        if match is None:
            match = find_next(doc.text, query, start=0)
        if match is None:
            self._notify(f"Not found: {query!r}", severity="warning")
            self.update_count()
            return
        new_m = replace_match(doc, match, bar.replacement)
        self._push_editor()
        self._last_end = new_m.end
        # Advance to the next occurrence after the replacement.
        nxt = find_next(doc.text, query, start=new_m.end)
        if nxt is None and new_m.end > 0:
            nxt = find_next(doc.text, query, start=0)
        if nxt is not None:
            self._select_range(nxt.start, nxt.end)
            self._last_end = nxt.end
        else:
            self._select_range(new_m.start, new_m.end)
        self._refresh_status()
        self.update_count()

    def replace_all(self) -> None:
        """Replace every match of the find string; empty replacement deletes."""
        bar = self._bar()
        if not bar.is_visible:
            self.open(replace=True)
            if not bar.query:
                self._notify(
                    "Enter a find string, then use Replace All", severity="warning"
                )
                return
        elif not bar.is_replace_mode:
            bar.expand_replace()
        query = bar.query
        if not query:
            self._notify("Enter a find string", severity="warning")
            return
        n = replace_all(self._document(), query, bar.replacement)
        self._push_editor()
        self._last_end = 0
        self._refresh_status()
        self.update_count()
        self._notify(f"Replaced {n} occurrence(s)")

    # --- highlights / count ------------------------------------------------

    def refresh_highlights(self) -> None:
        """Soft-highlight every match; the focused one stays bright via selection."""
        try:
            editor = self._editor()
            bar = self._bar()
        except Exception:
            return
        if not bar.is_visible or not bar.query:
            editor.clear_search_highlights()
            return
        editor.set_search_highlights(find_all(self._document().text, bar.query))

    def update_count(self) -> None:
        """Refresh the n/total badge on the find bar and the soft highlights."""
        try:
            bar = self._bar()
        except Exception:
            return
        if not bar.is_visible:
            self.refresh_highlights()
            return
        query = bar.query
        if not query:
            bar.set_match_count(None, 0)
            self.refresh_highlights()
            return
        matches = find_all(self._document().text, query)
        total = len(matches)
        try:
            self._editor().set_search_highlights(matches)
        except Exception:
            pass
        if total == 0:
            bar.set_match_count(None, 0)
            return
        cursor = self._cursor_index()
        current: int | None = None
        for i, m in enumerate(matches):
            if (
                m.start <= cursor < m.end
                or m.start == cursor
                or (self._last_end and m.end == self._last_end)
            ):
                current = i + 1
                break
        if current is None and self._last_end:
            for i, m in enumerate(matches):
                if m.end == self._last_end:
                    current = i + 1
                    break
        bar.set_match_count(current, total)

"""SpellController — owns spellcheck state and coordination.

The mirror of FindController for spelling. It owns the Speller, the on/off flag,
the debounce timer, and the walk-through position, and it coordinates the editor,
the SpellBar walk-through, and the caret suggestion popup. The pure work
(find_misspellings, the Speller dictionary) stays in domain/spellcheck.

Framework primitives it can't do itself (a debounce timer, a background thread
for the dictionary scan, the modal popup, the screen size) are injected as
callables, so there's no app import and the coordination logic is testable with
stubs.
"""

from __future__ import annotations

from typing import Callable, Optional

from markstar.domain.markdown import word_bounds
from markstar.domain.spellcheck import Speller, find_misspellings
from markstar.ui.suggest_popup import MAX_ROWS, POPUP_WIDTH, SuggestPopup


class SpellController:
    def __init__(
        self,
        *,
        prefs,
        get_editor: Callable[[], object],
        get_bar: Callable[[], object],
        get_document: Callable[[], object],
        select_range: Callable[[int, int], None],
        notify: Callable[..., None],
        set_timer: Callable[..., object],
        run_worker: Callable[..., object],
        call_from_thread: Callable[..., object],
        push_screen_wait: Callable[..., object],
        screen_size: Callable[[], object],
    ) -> None:
        self._prefs = prefs
        self._editor = get_editor
        self._bar = get_bar
        self._document = get_document
        self._select_range = select_range
        self._notify = notify
        self._set_timer = set_timer
        self._run_worker = run_worker
        self._call_from_thread = call_from_thread
        self._push_screen_wait = push_screen_wait
        self._screen_size = screen_size

        self._speller = Speller(prefs.spell_added, language=prefs.spell_language)
        self._enabled = prefs.spellcheck
        self._timer = None
        # (start, end, word) of the misspelling the walk-through is parked on.
        self._current: tuple[int, int, str] | None = None

    # --- accessors (kept for the app + tests) ------------------------------

    @property
    def speller(self) -> Speller:
        return self._speller

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def current(self) -> Optional[tuple[int, int, str]]:
        return self._current

    def prime(self) -> None:
        self._speller.prime()

    # --- underline pass (debounced, threaded) ------------------------------

    def toggle(self) -> None:
        self._enabled = not self._enabled
        self._prefs.spellcheck = self._enabled
        self._prefs.save()
        if self._enabled:
            self.run()
        else:
            try:
                self._editor().clear_spell_highlights()
            except Exception:
                pass
        self._notify(f"Spellcheck {'on' if self._enabled else 'off'}")

    def schedule(self) -> None:
        """Debounce a re-check after the last edit (prefs.spellcheck_ms)."""
        if not self._enabled:
            return
        if self._timer is not None:
            self._timer.stop()
        delay = max(0.1, self._prefs.spellcheck_ms / 1000)
        self._timer = self._set_timer(delay, self.run)

    def run(self) -> None:
        if not self._enabled:
            return
        text = self._document().text

        def work() -> None:
            # The dictionary loads lazily here — off the UI thread on first use.
            matches = find_misspellings(text, self._speller.known)
            self._call_from_thread(self._apply, matches)

        self._run_worker(work, thread=True, exclusive=True, group="spell")

    def _apply(self, matches) -> None:
        try:
            self._editor().set_spell_highlights(matches)
        except Exception:
            pass

    # --- caret suggestion popup --------------------------------------------

    def suggest(self) -> None:
        """Pop a suggestion list at the caret for the misspelled word under it."""
        editor = self._editor()
        row, col = editor.cursor_location
        line = editor.document.get_line(row)
        a, b = word_bounds(line, col)
        if a == b:
            self._notify("Put the caret on a word first")
            return
        word = line[a:b]
        if self._speller.known(word):
            self._notify(f"“{word}” is spelled correctly")
            return
        # Open even with no suggestions — Add/Ignore are always available.
        suggestions = self._speller.suggestions(word)
        off = editor.cursor_screen_offset
        self._run_worker(self.suggest_async(row, a, b, word, suggestions, off))

    async def suggest_async(self, row, a, b, word, suggestions, off) -> None:
        popup_h = min(len(suggestions) + 2, MAX_ROWS)
        size = self._screen_size()
        y = off.y + 1
        if y + popup_h > size.height:
            y = max(0, off.y - popup_h)
        x = max(0, min(off.x, size.width - POPUP_WIDTH))
        chosen = await self._push_screen_wait(SuggestPopup(word, suggestions, (x, y)))
        if not chosen:
            return
        editor = self._editor()
        if chosen == SuggestPopup.ADD:
            self._speller.add(word)
            self._prefs.spell_added = self._speller.added_words
            self._prefs.save()
            self._notify(f"Added “{word}” to your dictionary")
            self.run()  # drop the underline now that it's known
            editor.focus()
            return
        if chosen == SuggestPopup.IGNORE:
            self._speller.ignore(word)
            self._notify(f"Ignoring “{word}” this session")
            self.run()
            editor.focus()
            return
        # Recompute the span (nothing else could edit while the modal was up).
        line = editor.document.get_line(row)
        if line[a:b] == word:
            editor.replace(chosen, (row, a), (row, b))
        editor.focus()

    # --- SpellBar walk-through ---------------------------------------------

    def start_walk(self) -> None:
        """Open the spelling bar and step to the first misspelling."""
        self.goto(0)

    def goto(self, from_index: int) -> None:
        """Focus the first misspelling at/after ``from_index``; finish if none."""
        doc = self._document()
        issues = find_misspellings(doc.text, self._speller.known)
        try:
            self._editor().set_spell_highlights(issues)
        except Exception:
            pass
        bar = self._bar()
        for i, m in enumerate(issues):
            if m.start >= from_index:
                word = doc.text[m.start : m.end]
                self._current = (m.start, m.end, word)
                self._select_range(m.start, m.end)
                bar.show_word(word, self._speller.suggestions(word), i + 1, len(issues))
                return
        self._current = None
        if bar.is_visible:
            bar.hide()
        self._notify("No misspellings" if not issues else "Spelling check complete")
        try:
            self._editor().focus()
        except Exception:
            pass

    def on_request(self, action: str, value: str) -> None:
        if self._current is None:
            return
        start, end, word = self._current
        editor = self._editor()
        if action == "change":
            try:
                s = editor.document.get_location_from_index(start)
                e = editor.document.get_location_from_index(end)
                editor.replace(value, s, e)
            except Exception:
                return
            self.goto(start + len(value))
        elif action == "skip":
            self._speller.ignore(word)
            self.goto(end)
        elif action == "add":
            self._speller.add(word)
            self._prefs.spell_added = self._speller.added_words
            self._prefs.save()
            self.goto(end)

    def on_dismissed(self) -> None:
        self._current = None
        try:
            self._editor().focus()
        except Exception:
            pass

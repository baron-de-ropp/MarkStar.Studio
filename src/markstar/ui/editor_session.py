"""EditorSession — the single seam between the active Document and the editor.

The app keeps two representations of the current file's text: the ``Document``
(source of truth: undo history, path, dirty flag) and the live ``TextArea``
widget the user types into. Historically every command that read
``self.document.text`` had to remember to call ``_sync_document_from_editor()``
first, because the editor's change event is queued (async) and the Document
could lag a keystroke behind.

This object owns that invariant so callers can't forget it:

* ``document`` / ``text`` — always current: reading them flushes the editor's
  live text into the active Document first.
* ``flush()`` — editor → Document, synchronous and idempotent; returns whether
  the text actually changed (so the change handler can gate its side effects).
* ``load_active()`` — Document → editor, guarded so the resulting change event
  doesn't echo back as a fresh user edit.

It is UI-adjacent (it drives a TextArea) but holds no widgets directly — the
editor is fetched lazily via a callable, so the session can exist before the
editor is mounted and survive editor teardown in tests.
"""

from __future__ import annotations

from typing import Callable, Optional

from markstar.domain.document import Document
from markstar.domain.workspace import Workspace


class EditorSession:
    def __init__(
        self, workspace: Workspace, get_editor: Callable[[], object]
    ) -> None:
        self._workspace = workspace
        self._get_editor = get_editor
        self._loading = False

    @property
    def loading(self) -> bool:
        """True while ``load_active`` is pushing text into the editor — used to
        ignore the editor change event it provokes."""
        return self._loading

    def _editor(self):
        try:
            return self._get_editor()
        except Exception:
            return None

    @property
    def document(self) -> Document:
        """The active Document, guaranteed consistent with the live editor."""
        self.flush()
        return self._workspace.active

    @property
    def text(self) -> str:
        return self.document.text

    def flush(self) -> bool:
        """Pull the editor's live text into the active Document.

        Synchronous and idempotent. Returns True iff the Document text changed
        (nothing to do while loading, or when there is no editor yet)."""
        if self._loading:
            return False
        editor = self._editor()
        if editor is None:
            return False
        active = self._workspace.active
        if editor.text != active.text:
            active.set_text(editor.text)
            return True
        return False

    def load_active(self) -> None:
        """Push the active Document's text into the editor, guarding the change
        event so it isn't mistaken for a user edit."""
        editor = self._editor()
        if editor is None:
            return
        self._loading = True
        try:
            editor.load_text(self._workspace.active.text)
        finally:
            self._loading = False

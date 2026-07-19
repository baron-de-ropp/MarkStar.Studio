"""EditorSession — the Document <-> editor text invariant, tested with a stub."""

from __future__ import annotations

from markstar.domain.workspace import Workspace
from markstar.ui.editor_session import EditorSession


class _StubEditor:
    """Minimal stand-in for a TextArea: just the .text / load_text() the session
    actually touches."""

    def __init__(self, text: str = "") -> None:
        self.text = text

    def load_text(self, text: str) -> None:
        self.text = text


def _session(text: str = ""):
    ws = Workspace()
    ed = _StubEditor(text)
    return EditorSession(ws, lambda: ed), ws, ed


def test_document_property_flushes_editor_text() -> None:
    session, ws, ed = _session()
    ed.text = "typed into the editor"
    # Reading .document must pull the editor's live text into the active doc.
    assert session.document.text == "typed into the editor"
    assert ws.active.text == "typed into the editor"


def test_flush_reports_whether_it_changed() -> None:
    session, ws, ed = _session()
    ed.text = "new"
    assert session.flush() is True   # editor differed from doc
    assert session.flush() is False  # now in sync → no-op


def test_load_active_pushes_and_suppresses_echo() -> None:
    session, ws, ed = _session()
    ws.active.set_text("from the document")
    session.load_active()
    assert ed.text == "from the document"
    # While loading, flush must be inert (the change is not a user edit).
    session._loading = True
    ed.text = "spurious echo"
    assert session.flush() is False
    assert ws.active.text == "from the document"


def test_no_editor_is_a_safe_noop() -> None:
    ws = Workspace()
    session = EditorSession(ws, lambda: (_ for _ in ()).throw(RuntimeError))
    assert session.flush() is False       # getter raises → treated as no editor
    session.load_active()                 # must not raise
    assert session.document is ws.active  # still returns the active doc

"""Make ``WrappedDocument.height`` O(1) instead of O(document).

Textual computes the wrapped height as ``sum(len(offsets) + 1 for offsets in
self._wrap_offsets)`` — a pass over every line of the document, uncached. That
would be fine if it were read occasionally, but ``TextArea._render_line`` reads
it for *every rendered row* to decide whether the row is past the end of the
document. On a 4,000-line manuscript that is ~25 passes over 4,000 lines on
every keystroke, and it is the single largest cost of typing in a long file.

The same object already maintains ``_offset_to_line_info``: one entry per
wrapped row, rebuilt and patched by exactly the same code that maintains
``_wrap_offsets``. Its length *is* the height, and reading it is O(1). Verified
equal across short documents, wrapped documents, insertions, deletions, newline
splits, terminal re-wraps in both directions, and with soft wrap off.

Applied process-wide at import, in the manner of ui/scrollbar.install().
"""

from __future__ import annotations

from textual.document._wrapped_document import WrappedDocument

_PATCHED = "_markstar_fast_height"


def _height(self: WrappedDocument) -> int:
    """The height of the wrapped document (O(1))."""
    try:
        return len(self._offset_to_line_info)
    except AttributeError:
        # A future Textual could drop the offset map; fall back to the
        # original definition rather than break the editor.
        return sum(len(offsets) + 1 for offsets in self._wrap_offsets)


def install() -> None:
    """Swap in the O(1) height. Idempotent."""
    if getattr(WrappedDocument, _PATCHED, False):
        return
    WrappedDocument.height = property(_height)
    setattr(WrappedDocument, _PATCHED, True)

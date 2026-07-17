"""Document buffer with op-based undo/redo (P0)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class _ReplaceOp:
    """Replace text[start:end] with ``text`` (inverse stores the previous slice)."""

    start: int
    end: int
    text: str
    previous: str


class Document:
    """In-memory UTF-8 document; source of truth for one open file.

    Interface (deep module):
    - insert / delete / replace / set_text
    - undo / redo (linear; edit after undo clears redo)
    - save / load / mark_saved
    - word_count
    """

    def __init__(self, text: str = "", path: Optional[Path] = None) -> None:
        self._text = text
        self.path = Path(path) if path is not None else None
        self._dirty = False
        self._undo: list[_ReplaceOp] = []
        self._redo: list[_ReplaceOp] = []

    # --- read API -----------------------------------------------------------

    @property
    def text(self) -> str:
        return self._text

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def word_count(self) -> int:
        return len(self._text.split())

    # --- mutations ----------------------------------------------------------

    def insert(self, index: int, text: str) -> None:
        if not text:
            return
        self._apply(_ReplaceOp(start=index, end=index, text=text, previous=""))

    def delete(self, start: int, end: int) -> None:
        if start == end:
            return
        if start > end:
            start, end = end, start
        previous = self._text[start:end]
        self._apply(_ReplaceOp(start=start, end=end, text="", previous=previous))

    def replace(self, start: int, end: int, text: str) -> None:
        if start > end:
            start, end = end, start
        previous = self._text[start:end]
        if previous == text:
            return
        self._apply(_ReplaceOp(start=start, end=end, text=text, previous=previous))

    def set_text(self, text: str) -> None:
        self.replace(0, len(self._text), text)

    def undo(self) -> bool:
        if not self._undo:
            return False
        op = self._undo.pop()
        inverse = _ReplaceOp(
            start=op.start,
            end=op.start + len(op.text),
            text=op.previous,
            previous=op.text,
        )
        self._apply_raw(inverse)
        self._redo.append(op)
        self._dirty = True
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        op = self._redo.pop()
        self._apply_raw(op)
        self._undo.append(op)
        self._dirty = True
        return True

    def mark_saved(self) -> None:
        self._dirty = False

    # --- persistence --------------------------------------------------------

    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("path is required to save a document without an existing path")
        target.write_text(self._text, encoding="utf-8")
        self.path = target
        self.mark_saved()
        return target

    @classmethod
    def load(cls, path: Path | str) -> Document:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        doc = cls(text=text, path=p)
        doc._dirty = False
        return doc

    # --- internals ----------------------------------------------------------

    def _apply(self, op: _ReplaceOp) -> None:
        self._apply_raw(op)
        self._undo.append(op)
        self._redo.clear()
        self._dirty = True

    def _apply_raw(self, op: _ReplaceOp) -> None:
        self._text = self._text[: op.start] + op.text + self._text[op.end :]

"""Multi-document workspace (open tabs)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from prose.domain.document import Document


class Workspace:
    """Ordered list of open documents with one active tab.

    Deep module: open/close/switch only — UI renders from ``documents`` +
    ``active_index``.
    """

    def __init__(self, document: Optional[Document] = None) -> None:
        self._docs: list[Document] = [document if document is not None else Document()]
        self._active = 0

    @property
    def documents(self) -> list[Document]:
        return list(self._docs)

    @property
    def active_index(self) -> int:
        return self._active

    @property
    def active(self) -> Document:
        return self._docs[self._active]

    @property
    def count(self) -> int:
        return len(self._docs)

    def new_document(self, text: str = "", path: Optional[Path] = None) -> Document:
        doc = Document(text=text, path=path)
        self._docs.append(doc)
        self._active = len(self._docs) - 1
        return doc

    def open_document(self, document: Document) -> Document:
        """Focus existing tab with same path, or append a new tab.

        If the only tab is an empty untitled buffer, replace it (editor-style).
        """
        if document.path is not None:
            target = document.path.resolve()
            for i, doc in enumerate(self._docs):
                if doc.path is not None and doc.path.resolve() == target:
                    self._active = i
                    return self.active
        if (
            len(self._docs) == 1
            and self._docs[0].path is None
            and self._docs[0].text == ""
            and not self._docs[0].dirty
        ):
            self._docs[0] = document
            self._active = 0
            return self.active
        self._docs.append(document)
        self._active = len(self._docs) - 1
        return self.active

    def open_path(self, path: Path | str) -> Document:
        p = Path(path)
        if p.exists():
            return self.open_document(Document.load(p))
        doc = Document(path=p)
        return self.open_document(doc)

    def set_active(self, index: int) -> Document:
        if index < 0 or index >= len(self._docs):
            raise IndexError(f"tab index out of range: {index}")
        self._active = index
        return self.active

    def next_tab(self) -> Document:
        self._active = (self._active + 1) % len(self._docs)
        return self.active

    def prev_tab(self) -> Document:
        self._active = (self._active - 1) % len(self._docs)
        return self.active

    def close_active(self) -> Document:
        """Close the active tab. Always leaves at least one (possibly empty) document."""
        if len(self._docs) == 1:
            self._docs[0] = Document()
            self._active = 0
            return self.active
        del self._docs[self._active]
        if self._active >= len(self._docs):
            self._active = len(self._docs) - 1
        return self.active

    def close_all(self) -> Document:
        self._docs = [Document()]
        self._active = 0
        return self.active

    def dirty_documents(self) -> list[Document]:
        """Open buffers with unsaved changes."""
        return [doc for doc in self._docs if doc.dirty]

    @property
    def has_dirty(self) -> bool:
        return any(doc.dirty for doc in self._docs)

"""Project panel — a quiet, Yazi-like file tree overlaid on the left.

Overlay (does not shift the prose), ~30 cols, Markdown-focused. Opening a file
(Enter / click) posts nothing special — the app listens for the tree's
``FileSelected`` message and opens it in a tab. See design spec §5.5.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DirectoryTree, Static

_SHOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd", ".txt"}


class WriterTree(DirectoryTree):
    """DirectoryTree filtered for writers: directories + Markdown/txt files,
    hidden dot-entries omitted. Quiet ASCII outline icons (spec: no emoji)."""

    ICON_NODE = "▸ "           # collapsed folder
    ICON_NODE_EXPANDED = "▾ "  # expanded folder
    ICON_FILE = "· "           # file

    def filter_paths(self, paths):  # type: ignore[override]
        out = []
        for p in paths:
            try:
                if p.name.startswith("."):
                    continue
                if p.is_dir() or p.suffix.lower() in _SHOWN_SUFFIXES:
                    out.append(p)
            except OSError:
                continue
        return out


class ProjectPanel(Vertical):
    """Left overlay: project root header + filtered file tree."""

    DEFAULT_CSS = """
    ProjectPanel {
        dock: left;
        layer: overlay;
        width: 30;
        height: 100%;
        display: none;
        background: $surface;
        border-right: solid $accent 35%;
    }

    ProjectPanel.visible {
        display: block;
    }

    ProjectPanel #project-header {
        height: 1;
        width: 100%;
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
        background: $accent 18%;
    }

    ProjectPanel WriterTree {
        width: 100%;
        height: 1fr;
        padding: 0 0 0 1;
        background: $surface;
        color: $text-muted;
        scrollbar-size-vertical: 1;
    }

    ProjectPanel WriterTree > .directory-tree--folder {
        color: $text-muted;
    }
    ProjectPanel WriterTree > .directory-tree--file {
        color: $text;
    }
    ProjectPanel WriterTree > .tree--guides,
    ProjectPanel WriterTree > .tree--guides-hover,
    ProjectPanel WriterTree > .tree--guides-selected {
        color: $text-muted 30%;
    }
    ProjectPanel WriterTree > .tree--cursor {
        background: $accent 45%;
        color: $text;
    }
    """

    def __init__(self, root: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._root = root

    def compose(self) -> ComposeResult:
        yield Static(self._header_text(self._root), id="project-header")
        yield WriterTree(str(self._root), id="project-tree")

    def _header_text(self, root: Path) -> str:
        name = root.name or str(root)
        return f"  {name}"

    @property
    def is_open(self) -> bool:
        return self.has_class("visible")

    def open(self) -> None:
        self.add_class("visible")

    def close(self) -> None:
        self.remove_class("visible")

    def focus_tree(self) -> None:
        try:
            self.query_one(WriterTree).focus()
        except Exception:
            pass

    def set_root(self, root: Path) -> None:
        self._root = root
        try:
            tree = self.query_one(WriterTree)
            tree.path = str(root)
            tree.reload()
        except Exception:
            pass
        try:
            self.query_one("#project-header", Static).update(self._header_text(root))
        except Exception:
            pass

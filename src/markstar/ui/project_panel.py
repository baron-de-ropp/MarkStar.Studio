"""Project panel — a quiet, Yazi-like file tree overlaid on the left.

Overlay (does not shift the prose), Markdown-focused. Shows the *contents* of
the project root (no collapsible root node). Files already open in tabs are
brightened; the active file is highlighted. Selecting a file (Enter / click)
posts ``FileSelected``, which the app opens in a tab.
"""

from __future__ import annotations

from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DirectoryTree, Rule, Static

from markstar.ui.themes import token

_SHOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd", ".txt"}


class WriterTree(DirectoryTree):
    """DirectoryTree filtered for writers: directories + Markdown/txt files,
    hidden dot-entries omitted. Quiet ASCII outline icons (spec: no emoji).
    Open files are brightened; the active file is highlighted."""

    ICON_NODE = "▸ "           # collapsed folder
    ICON_NODE_EXPANDED = "▾ "  # expanded folder
    ICON_FILE = "· "           # file

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._open_paths: set[str] = set()
        self._active_path: str | None = None

    def set_open_files(self, open_paths: set[str], active: str | None) -> None:
        self._open_paths = open_paths
        self._active_path = active
        self.refresh()

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

    def render_label(self, node, base_style: Style, style: Style) -> Text:
        label = super().render_label(node, base_style, style)
        data = getattr(node, "data", None)
        path = getattr(data, "path", None)
        if path is None:
            return label
        try:
            key = str(Path(path).resolve())
        except Exception:
            return label
        if key == self._active_path:
            label.stylize(Style(color=token(self.app, "hint-key"), bold=True))
        elif key in self._open_paths:
            label.stylize(Style(color=token(self.app, "foreground")))
        return label


class ProjectPanel(Vertical):
    """Left overlay: a thin top rule + the filtered file tree."""

    DEFAULT_CSS = """
    ProjectPanel {
        dock: left;
        layer: overlay;
        width: 40;
        height: 100%;
        display: none;
        /* Same chrome as the find/replace and spelling bars. */
        background: $boost;
        border-right: solid $accent 30%;
    }

    ProjectPanel.visible {
        display: block;
    }

    ProjectPanel #project-rule {
        color: $accent 30%;
        margin: 0;
        padding: 0;
    }

    ProjectPanel WriterTree {
        width: 100%;
        height: 1fr;
        padding: 0 0 0 1;
        background: $boost;
        color: $text-muted;
        scrollbar-size-vertical: 1;
        scrollbar-background: $boost;
        scrollbar-background-hover: $boost;
        scrollbar-background-active: $boost;
        scrollbar-color: $text-muted 12%;
        scrollbar-color-hover: $text-muted 45%;
        scrollbar-color-active: $text-muted 55%;
        scrollbar-corner-color: $boost;
    }

    /* Folders + closed files: dim. Open/active files are brightened in
       render_label. Tree connector guides: very faint. */
    ProjectPanel WriterTree > .directory-tree--folder {
        color: $text-muted;
    }
    ProjectPanel WriterTree > .directory-tree--file {
        color: $text-muted;
    }
    ProjectPanel WriterTree > .tree--guides,
    ProjectPanel WriterTree > .tree--guides-hover,
    ProjectPanel WriterTree > .tree--guides-selected {
        color: $text-muted 18%;
    }
    ProjectPanel WriterTree > .tree--cursor {
        background: $accent 40%;
        color: $text;
    }
    """

    def __init__(self, root: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._root = root

    def compose(self) -> ComposeResult:
        yield Rule(id="project-rule")
        yield WriterTree(str(self._root), id="project-tree")

    def on_mount(self) -> None:
        try:
            self.query_one(WriterTree).show_root = False  # show contents, not root
        except Exception:
            pass

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

    def set_open_files(self, open_paths: set[str], active: str | None) -> None:
        try:
            self.query_one(WriterTree).set_open_files(open_paths, active)
        except Exception:
            pass

    def set_root(self, root: Path) -> None:
        self._root = root
        try:
            tree = self.query_one(WriterTree)
            tree.path = str(root)
            tree.show_root = False
            tree.reload()
        except Exception:
            pass

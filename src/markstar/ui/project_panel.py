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
from textual.widgets import DirectoryTree

from markstar.ui.themes import token

# Files MarkStar can open/edit as documents. Everything else (images, PDFs,
# binaries, source files) still shows in the tree as a link/embed target, but is
# rendered fainter and can't be opened in an editor tab.
MARKDOWN_EXTS = frozenset(
    {".md", ".markdown", ".mdown", ".mkd", ".mdx", ".mdtext", ".txt"}
)


def is_openable(path) -> bool:
    """True if ``path`` is a Markdown/plain-text document MarkStar can edit."""
    return Path(path).suffix.lower() in MARKDOWN_EXTS


class WriterTree(DirectoryTree):
    """DirectoryTree for writers: directories + all files (so images, PDFs, and
    other link/embed targets are visible), hidden dot-entries omitted. Quiet
    ASCII outline icons (spec: no emoji). Open files are brightened; the active
    file is highlighted."""

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
                out.append(p)
            except OSError:
                continue
        return out

    def render_label(self, node, base_style: Style, style: Style) -> Text:
        label = super().render_label(node, base_style, style)
        # Returned label is "icon(2 chars) + name". Force the brightness tier,
        # overriding DirectoryTree's default bold/bright folder styling:
        #   non-openable file      → faintest (can't be edited; link target only)
        #   folders + closed files → dim (clearly below the editor text)
        #   open file (in a tab)   → brighter name
        #   active file            → brighter name, and its bullet in the accent
        key = None
        path = getattr(getattr(node, "data", None), "path", None)
        if path is not None:
            try:
                key = str(Path(path).resolve())
            except Exception:
                key = None
        # A non-openable file (image/PDF/etc.) reads faintest and never bold.
        if path is not None and not node.allow_expand and not is_openable(path):
            label.stylize(Style(color=token(self.app, "rule"), bold=False))
            return label
        bright = token(self.app, "tab-active")
        dim = token(self.app, "tab-inactive")
        if key is not None and key == self._active_path:
            label.stylize(Style(color=bright, bold=False))
            if len(label) >= 2:  # bullet only → accent
                label.stylize(Style(color=token(self.app, "hint-key"), bold=True), 0, 2)
        elif key is not None and key in self._open_paths:
            label.stylize(Style(color=bright, bold=False))
        else:  # folders + closed files → dim, never bold
            label.stylize(Style(color=dim, bold=False))
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
        background: $boost;
        /* A 3-sided box (top/right/bottom) that "flies out" from the screen
           edge; Textual draws the ┐ ┘ corners. The project name rides the top. */
        border-top: solid $accent 40%;
        border-right: solid $accent 40%;
        border-bottom: solid $accent 40%;
        border-title-color: $text;
        border-title-align: left;
    }

    ProjectPanel.visible {
        display: block;
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
    /* Keep the indentation guides faint in every state. Textual's Tree brightens
       the SELECTED node's guides when the tree is blurred (and applies a
       text-style we must also clear), which lit them up bright white after focus
       left the panel. Cover both the focused and blurred variants. */
    ProjectPanel WriterTree > .tree--guides,
    ProjectPanel WriterTree > .tree--guides-hover,
    ProjectPanel WriterTree > .tree--guides-selected,
    ProjectPanel WriterTree:focus > .tree--guides,
    ProjectPanel WriterTree:focus > .tree--guides-hover,
    ProjectPanel WriterTree:focus > .tree--guides-selected {
        color: $text-muted 18%;
        text-style: none;
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
        yield WriterTree(str(self._root), id="project-tree")

    def on_mount(self) -> None:
        self.border_title = self._title(self._root)
        try:
            self.query_one(WriterTree).show_root = False  # show contents, not root
        except Exception:
            pass

    @staticmethod
    def _title(root: Path) -> str:
        return f" {root.name or root} "

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
        self.border_title = self._title(root)
        try:
            tree = self.query_one(WriterTree)
            tree.path = str(root)
            tree.show_root = False
            tree.reload()
        except Exception:
            pass

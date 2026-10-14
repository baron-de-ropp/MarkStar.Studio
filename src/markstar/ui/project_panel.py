"""Project panel — a quiet, Yazi-like file tree overlaid on the left.

Overlay (does not shift the prose), Markdown-focused. Shows the *contents* of
the project root (no collapsible root node). Files already open in tabs are
brightened; the active file is highlighted. Selecting a file (Enter / click)
posts ``FileSelected``, which the app opens in a tab.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DirectoryTree

from markstar.domain.filewalk import MARKDOWN_EXTS, is_openable  # noqa: F401 (re-export)
from markstar.ui.themes import token


def _file_icon(path: Path) -> str:
    """Quiet two-character glyph for a file kind (no emoji, no desktop icons)."""
    suffix = path.suffix.lower()
    if suffix in MARKDOWN_EXTS:
        return "# "
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}:
        return "* "
    if suffix == ".pdf":
        return "p "
    return "- "


class WriterTree(DirectoryTree):
    """DirectoryTree for writers: directories + all files (so images, PDFs, and
    other link/embed targets are visible), hidden dot-entries omitted. Quiet
    ASCII icons (folders ``+``/``-``, Markdown ``#``, images ``*``). Open files
    are brightened; the active file is highlighted."""

    ICON_NODE = "+ "           # collapsed folder
    ICON_NODE_EXPANDED = "- "  # expanded folder
    ICON_FILE = "# "           # default document; render_label may refine

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._open_paths: set[str] = set()
        self._active_path: str | None = None
        # No connector guide lines — indentation alone shows the hierarchy, and it
        # stays quiet. (Textual renders the ├──/└── elbows with an unflattened
        # alpha that falls back to bright white when the tree is blurred; turning
        # guides off avoids that entirely.)
        self.show_guides = False

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

    @work(thread=True, exit_on_error=False)
    def _load_directory(self, node):  # type: ignore[override]
        """Sort order within a folder: directories first, then openable
        (Markdown/text) files, then unsupported files — each group alphabetical."""
        from textual.worker import get_current_worker

        assert node.data is not None
        path = node.data.path.expanduser().resolve()
        return sorted(
            self.filter_paths(self._directory_content(path, get_current_worker())),
            key=lambda p: (
                not self._safe_is_dir(p),   # directories first
                not is_openable(p),         # then Markdown/text, then the rest
                p.name.lower(),             # alphabetical within each group
            ),
        )

    @staticmethod
    def _child_named(node, name: str):
        for child in node.children:
            path = getattr(getattr(child, "data", None), "path", None)
            if path is not None and Path(path).name == name:
                return child
        return None

    async def reveal_path(self, target: Path, *, ticks: int = 40) -> bool:
        """Expand down to ``target`` and park the cursor on it.

        Children load in a background thread, so each level is polled until it
        populates rather than assumed present. Moves the cursor rather than
        selecting: selecting a file posts ``FileSelected``, which the app would
        answer by opening the file we are merely trying to point at.
        """
        try:
            root = Path(self.path).expanduser().resolve()
            target = Path(target).expanduser().resolve()
            rel = target.relative_to(root)
        except (ValueError, OSError):
            return False  # outside the project — nothing to reveal

        node = self.root
        for part in rel.parts:
            if not node.is_expanded:
                node.expand()
            child = None
            for _ in range(ticks):
                child = self._child_named(node, part)
                if child is not None:
                    break
                await asyncio.sleep(0.02)
            if child is None:
                return False
            node = child
        try:
            self.move_cursor(node)
            self.scroll_to_node(node)
        except Exception:
            return False
        return True

    def render_label(self, node, base_style: Style, style: Style) -> Text:
        label = super().render_label(node, base_style, style)
        # Returned label is "icon(2 chars) + name". Force the brightness tier,
        # overriding DirectoryTree's default bold/bright folder styling:
        #   non-openable file      → faintest (can't be edited; link target only)
        #   folders + closed files → dim (clearly below the editor text)
        #   open file (in a tab)   → brighter name
        #   active file            → brighter name, and its icon in the accent
        key = None
        path = getattr(getattr(node, "data", None), "path", None)
        if path is not None:
            try:
                key = str(Path(path).resolve())
            except Exception:
                key = None
            # Swap the generic file icon for a quiet type glyph.
            if not node.allow_expand and len(label) >= 2:
                icon = _file_icon(Path(path))
                name = label.plain[2:]
                label = Text(icon + name)
        # A non-openable file (image/PDF/etc.) reads faintest and never bold.
        if path is not None and not node.allow_expand and not is_openable(path):
            label.stylize(Style(color=token(self.app, "rule"), bold=False))
            return label
        bright = token(self.app, "tab-active")
        dim = token(self.app, "tab-inactive")
        if key is not None and key == self._active_path:
            label.stylize(Style(color=bright, bold=False))
            if len(label) >= 2:  # icon only → accent
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
        border-title-align: center;
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
        scrollbar-size-horizontal: 1;
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
    /* Guide lines are disabled (WriterTree.show_guides = False). */
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

    def target_dir(self) -> Path:
        """Folder a new file should land in, based on the tree cursor.

        Cursor on a folder → that folder; on a file → its parent folder;
        nothing selected → the project root."""
        try:
            node = self.query_one(WriterTree).cursor_node
        except Exception:
            node = None
        data = getattr(node, "data", None) if node is not None else None
        path = getattr(data, "path", None)
        if path is not None:
            p = Path(path)
            try:
                if p.is_dir():
                    return p
                return p.parent
            except OSError:
                pass
        return self._root

    def refresh_tree(self) -> None:
        """Reload the file tree so newly created files appear."""
        try:
            self.query_one(WriterTree).reload()
        except Exception:
            pass

    async def reveal(self, path: Path) -> bool:
        """Point the tree at ``path`` (no-op when the panel is closed)."""
        if not self.is_open:
            return False
        try:
            return await self.query_one(WriterTree).reveal_path(path)
        except Exception:
            return False

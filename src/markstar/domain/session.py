"""Remember which files were open, and where the caret was in each.

Kept out of config.toml: preferences are a short file a writer might hand-edit,
and burying a churning list of tabs in it would spoil that. Serialisation is
hand-rolled TOML for the same reason config.py does it — no new dependency, and
a corrupt session file must never be able to stop the editor from starting.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MAX_FILES = 40  # a guard against a runaway session file, not a real limit


@dataclass(frozen=True)
class OpenFile:
    path: Path
    line: int = 0
    column: int = 0


@dataclass
class Session:
    files: list[OpenFile] = field(default_factory=list)
    active: int = 0
    project_root: Path | None = None

    @property
    def is_empty(self) -> bool:
        return not self.files

    def existing(self) -> "Session":
        """A copy holding only files still on disk, with ``active`` kept sane.

        A session restored after a file was renamed elsewhere should quietly
        open what survives rather than resurrect ghosts.
        """
        kept: list[OpenFile] = []
        new_active = 0
        for i, f in enumerate(self.files):
            try:
                if not f.path.is_file():
                    continue
            except OSError:
                continue
            if i == self.active:
                new_active = len(kept)
            kept.append(f)
        return Session(files=kept, active=new_active, project_root=self.project_root)


def _quote(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_toml(session: Session) -> str:
    lines = ["# MarkStar session — which files were open. Safe to delete.", ""]
    lines.append(f"active = {max(0, session.active)}")
    if session.project_root is not None:
        lines.append(f"project_root = {_quote(session.project_root)}")
    lines.append("")
    for f in session.files[:MAX_FILES]:
        lines.append("[[files]]")
        lines.append(f"path = {_quote(f.path)}")
        lines.append(f"line = {max(0, f.line)}")
        lines.append(f"column = {max(0, f.column)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def from_toml(data: bytes | str) -> Session:
    """Parse a session. Any malformed input yields an empty session, never raises."""
    try:
        parsed = tomllib.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
    except Exception:
        return Session()
    files: list[OpenFile] = []
    for entry in parsed.get("files", [])[:MAX_FILES]:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("path")
        if not isinstance(raw, str) or not raw:
            continue
        line = entry.get("line")
        column = entry.get("column")
        files.append(
            OpenFile(
                Path(raw),
                line if isinstance(line, int) and not isinstance(line, bool) else 0,
                column if isinstance(column, int) and not isinstance(column, bool) else 0,
            )
        )
    active = parsed.get("active")
    root = parsed.get("project_root")
    return Session(
        files=files,
        active=active if isinstance(active, int) and 0 <= active < len(files) else 0,
        project_root=Path(root) if isinstance(root, str) and root else None,
    )


def load(path: Path) -> Session:
    try:
        return from_toml(path.read_bytes())
    except OSError:
        return Session()


def save(path: Path, session: Session) -> None:
    """Write the session. Failure is never allowed to disturb the editor."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(to_toml(session), encoding="utf-8")
    except OSError:
        pass

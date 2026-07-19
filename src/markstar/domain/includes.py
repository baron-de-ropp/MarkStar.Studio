"""Include compilation: expand ``![[name]]`` references into one Markdown file.

A MarkStar extension (not CommonMark). In the editor an ``![[name]]`` is shown
as a token; on *compile* each reference is replaced with the referenced file's
text, recursively. Resolution is relative to the including file's directory,
then the project root. Missing files and cycles are reported, not fatal — the
output gets an HTML-comment marker where the include failed.

Pure and testable: ``compile_document`` takes injectable ``resolve`` and
``read_text`` callables. ``make_resolver`` builds a filesystem resolver.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

INCLUDE_RE = re.compile(r"!\[\[([^\]\n]+)\]\]")

_EXTS = ("", ".md", ".markdown", ".mdown", ".mkd", ".txt")

# resolve(name: str, base_dir: Path) -> Path | None
Resolver = Callable[[str, Path], "Path | None"]
Reader = Callable[["Path"], str]


def make_resolver(project_root: Path | None = None) -> Resolver:
    """Filesystem resolver: try ``name`` (and common extensions) relative to the
    including file's dir, then the project root, then as an absolute path."""

    def resolve(name: str, base_dir: Path) -> Path | None:
        name = name.strip()
        p = Path(name).expanduser()
        bases: list[Path] = [base_dir]
        if project_root is not None:
            bases.append(project_root)
        for ext in _EXTS:
            if p.is_absolute():
                cand = Path(str(p) + ext)
                if cand.is_file():
                    return cand
                continue
            for b in bases:
                cand = b / (name + ext)
                if cand.is_file():
                    return cand
        return None

    return resolve


def compile_document(
    text: str,
    base_dir: Path,
    resolve: Resolver,
    read_text: Reader | None = None,
    self_path: Path | None = None,
) -> tuple[str, list[str]]:
    """Return (expanded_text, errors). ``errors`` lists missing files / cycles."""
    reader: Reader = read_text or (lambda p: p.read_text(encoding="utf-8"))
    errors: list[str] = []
    seen: frozenset[Path] = frozenset()
    if self_path is not None:
        try:
            seen = frozenset({self_path.resolve()})
        except Exception:
            seen = frozenset()
    out = _expand(text, base_dir, resolve, reader, seen, errors)
    return out, errors


def _expand(
    text: str,
    base_dir: Path,
    resolve: Resolver,
    reader: Reader,
    seen: frozenset[Path],
    errors: list[str],
) -> str:
    def repl(m: "re.Match[str]") -> str:
        name = m.group(1).strip()
        path = resolve(name, base_dir)
        if path is None:
            errors.append(f"missing include: {name}")
            return f"<!-- missing include: {name} -->"
        try:
            rp = path.resolve()
        except Exception:
            rp = path
        if rp in seen:
            errors.append(f"include cycle: {name}")
            return f"<!-- include cycle: {name} -->"
        try:
            inc_text = reader(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot read include {name}: {exc}")
            return f"<!-- unreadable include: {name} -->"
        # Recurse; nested includes resolve relative to *their* file's directory.
        return _expand(
            inc_text, path.parent, resolve, reader, seen | {rp}, errors
        )

    return INCLUDE_RE.sub(repl, text)

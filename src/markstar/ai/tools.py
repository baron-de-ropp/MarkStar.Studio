"""Read-only project tools StarBot can call to ground its editorial feedback.

Three tools — list_files, grep, read_file — all scoped strictly to the project
root (no path escapes). Phase 2 is read-only; editing tools arrive in Phase 3.
Exposed as OpenAI-style function schemas plus an executor that runs a tool call
by name and returns a plain-text result for the model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# The model-facing tool definitions (OpenAI function-calling schema).
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List the project's files (relative paths) so you can "
            "see its structure. Optionally restrict to a subdirectory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subdir": {
                        "type": "string",
                        "description": "Optional subdirectory to list, relative to "
                        "the project root. Omit for the whole project.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search the project's text files for a regular "
            "expression. Returns matching lines as path:line: text. Best for "
            "continuity/consistency checks (names, places, established facts).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "A regex to search for."},
                    "subdir": {
                        "type": "string",
                        "description": "Optional subdirectory to limit the search to.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a project file's contents (with 1-based line "
            "numbers) so you can quote and reason about specific passages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the project root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

# Files StarBot treats as readable text (skip binaries/images).
_TEXT_EXTS = {".md", ".markdown", ".mdown", ".mkd", ".mdx", ".txt", ".text", ""}
_MAX_READ_BYTES = 200_000
_MAX_GREP_HITS = 200


class ProjectTools:
    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    # --- safety ------------------------------------------------------------

    def _resolve(self, rel: str) -> Path | None:
        """Resolve ``rel`` under the root, refusing anything that escapes it."""
        try:
            p = (self._root / (rel or "")).resolve()
        except Exception:
            return None
        if p != self._root and self._root not in p.parents:
            return None
        return p

    def _iter_files(self, base: Path):
        for p in sorted(base.rglob("*")):
            if p.is_dir():
                continue
            if any(part.startswith(".") for part in p.relative_to(self._root).parts):
                continue
            yield p

    # --- tools -------------------------------------------------------------

    def list_files(self, subdir: str = "") -> str:
        base = self._resolve(subdir)
        if base is None or not base.exists():
            return f"(no such directory: {subdir!r})"
        lines = []
        for p in self._iter_files(base if base.is_dir() else base.parent):
            rel = p.relative_to(self._root).as_posix()
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            lines.append(f"{rel}  ({size} bytes)")
        return "\n".join(lines) if lines else "(no files)"

    def grep(self, pattern: str, subdir: str = "") -> str:
        base = self._resolve(subdir)
        if base is None:
            return f"(no such directory: {subdir!r})"
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return f"(invalid regex: {exc})"
        hits = []
        for p in self._iter_files(base if base.is_dir() else base.parent):
            if p.suffix.lower() not in _TEXT_EXTS:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = p.relative_to(self._root).as_posix()
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel}:{i}: {line.strip()}")
                    if len(hits) >= _MAX_GREP_HITS:
                        hits.append(f"(stopped at {_MAX_GREP_HITS} matches)")
                        return "\n".join(hits)
        return "\n".join(hits) if hits else f"(no matches for {pattern!r})"

    def read_file(self, path: str) -> str:
        p = self._resolve(path)
        if p is None or not p.is_file():
            return f"(no such file: {path!r})"
        try:
            data = p.read_bytes()[:_MAX_READ_BYTES]
            text = data.decode("utf-8", errors="replace")
        except OSError as exc:
            return f"(could not read {path!r}: {exc})"
        return "\n".join(f"{i:>5}  {line}" for i, line in enumerate(text.splitlines(), 1))

    # --- dispatch ----------------------------------------------------------

    def execute(self, name: str, arguments_json: str) -> str:
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        if name == "list_files":
            return self.list_files(str(args.get("subdir", "") or ""))
        if name == "grep":
            return self.grep(str(args.get("pattern", "")), str(args.get("subdir", "") or ""))
        if name == "read_file":
            return self.read_file(str(args.get("path", "")))
        return f"(unknown tool: {name})"

    @staticmethod
    def summarize_call(name: str, arguments_json: str) -> str:
        """A short human line for the transcript, e.g. `grep "sigil"`."""
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            args = {}
        if name == "grep":
            return f'grep "{args.get("pattern", "")}"'
        if name == "read_file":
            return f'read {args.get("path", "")}'
        if name == "list_files":
            sub = args.get("subdir")
            return f"list {sub}" if sub else "list files"
        return name

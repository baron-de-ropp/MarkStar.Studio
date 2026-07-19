"""Edit proposals — StarBot proposes changes; the writer accepts or rejects.

Edits are line-based (StarBot reads files with line numbers, so it references
them precisely) and are NEVER applied by the tool — calling ``propose_edit`` only
registers a proposal and surfaces a diff card. The app applies an accepted edit
to the editor buffer (undoable), never silently to disk.
"""

from __future__ import annotations

from dataclasses import dataclass

# Statuses a proposal moves through.
PENDING, ACCEPTED, REJECTED, STALE = "pending", "accepted", "rejected", "stale"


@dataclass
class EditProposal:
    id: int
    path: str          # relative to the project root
    start_line: int    # 1-based, inclusive
    end_line: int      # 1-based, inclusive
    new_text: str
    reason: str
    old_text: str
    status: str = PENDING


EDIT_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "propose_edit",
        "description": (
            "Propose replacing a range of lines in a project file with new text. "
            "The change is NOT applied automatically — the writer reviews it and "
            "accepts or rejects. Use line numbers from read_file. Keep each "
            "proposal small and surgical (one distinct change); call this once per "
            "change. Always explain the change in `reason`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the project root.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to replace (1-based, inclusive).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to replace (1-based, inclusive).",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text for those lines (no trailing newline).",
                },
                "reason": {
                    "type": "string",
                    "description": "A short explanation of why this change helps.",
                },
            },
            "required": ["path", "start_line", "end_line", "new_text", "reason"],
        },
    },
}


def extract_lines(text: str, start: int, end: int) -> str:
    """The text of lines [start, end] (1-based, inclusive) from ``text``."""
    lines = text.split("\n")
    s = max(1, start)
    e = min(len(lines), end)
    if s > e:
        return ""
    return "\n".join(lines[s - 1 : e])

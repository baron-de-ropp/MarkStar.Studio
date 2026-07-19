"""EditCard — a proposed edit shown in the StarBot transcript, with accept/reject.

Displays the line range, a red/green diff (old → new), the reason, and two
buttons. Clicking posts ``Accepted`` / ``Rejected`` (with the proposal id); the
app applies or discards and then calls ``mark`` to freeze the card's outcome.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

from markstar.ai.edits import ACCEPTED, REJECTED
from markstar.ui.themes import token

_MAX_DIFF_LINES = 12  # keep a giant proposal from flooding the panel


class EditCard(Vertical):
    DEFAULT_CSS = """
    EditCard {
        height: auto; margin: 0 0 1 0; padding: 0 1;
        background: $boost; border: round $accent 40%;
    }
    EditCard .ec-head { height: auto; text-style: bold; color: $text-muted; }
    EditCard .ec-diff { height: auto; }
    EditCard .ec-reason { height: auto; color: $text-muted; padding: 1 0 0 0; }
    EditCard #ec-buttons { height: auto; align-horizontal: right; padding-top: 1; }
    EditCard #ec-buttons Button {
        border: none; height: 1; min-width: 0; margin: 0 0 0 3;
        background: $boost; color: $text-muted;
    }
    EditCard #ec-buttons Button:hover { color: $text; }
    """

    class Accepted(Message):
        def __init__(self, proposal_id: int) -> None:
            self.proposal_id = proposal_id
            super().__init__()

    class Rejected(Message):
        def __init__(self, proposal_id: int) -> None:
            self.proposal_id = proposal_id
            super().__init__()

    def __init__(self, proposal) -> None:
        super().__init__()
        self._p = proposal

    def compose(self) -> ComposeResult:
        dim = token(self, "rule")
        yield Static(self._head_markup(), classes="ec-head", markup=True)
        yield Static(self._diff_markup(), classes="ec-diff", markup=True)
        if self._p.reason:
            yield Static(f"[{dim}]{_esc(self._p.reason)}[/]", classes="ec-reason", markup=True)
        with Horizontal(id="ec-buttons"):
            yield Button("✓ accept", id="ec-accept")
            yield Button("✗ reject", id="ec-reject")

    def _head_markup(self) -> str:
        mut = token(self, "tab-inactive")
        return f"[{mut}]{_esc(self._p.path)} · lines {self._p.start_line}-{self._p.end_line}[/]"

    def _diff_markup(self) -> str:
        red = token(self, "error")
        grn = token(self, "success")
        lines: list[str] = []
        old = (self._p.old_text or "").split("\n")
        new = (self._p.new_text or "").split("\n")
        for ln in old[:_MAX_DIFF_LINES]:
            lines.append(f"[{red}]- {_esc(ln)}[/]")
        if len(old) > _MAX_DIFF_LINES:
            lines.append(f"[{red}]  …[/]")
        for ln in new[:_MAX_DIFF_LINES]:
            lines.append(f"[{grn}]+ {_esc(ln)}[/]")
        if len(new) > _MAX_DIFF_LINES:
            lines.append(f"[{grn}]  …[/]")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "ec-accept":
            self.post_message(self.Accepted(self._p.id))
        elif event.button.id == "ec-reject":
            self.post_message(self.Rejected(self._p.id))

    def mark(self, status: str) -> None:
        """Freeze the card after the writer decides."""
        self._p.status = status
        color = token(self, "success") if status == ACCEPTED else token(self, "error")
        label = "✓ accepted" if status == ACCEPTED else "✗ rejected"
        try:
            self.query_one(".ec-head", Static).update(
                f"[{color}]{label}[/]  {self._head_markup()}"
            )
            for b in self.query("Button"):
                b.disabled = True
        except Exception:
            pass


def _esc(text: str) -> str:
    return (text or "").replace("[", "\\[")

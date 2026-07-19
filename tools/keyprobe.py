"""Key delivery probe — run in the SAME terminal you use Prose in.

    cd ~/Applications/prose
    .venv/bin/python tools/keyprobe.py

Press the chords the handoff cares about and read what actually arrives:

    Enter, Ctrl+Enter, Ctrl+Shift+Enter
    Ctrl+R, Ctrl+Shift+R
    F4, Ctrl+Shift+A, Ctrl+Shift+L, Ctrl+Shift+Up

If Ctrl+Shift+Enter shows up as `ctrl+enter`, and Ctrl+Shift+R as
`ctrl+r`, then Shift is not representable in this terminal (legacy
encoding) — no rebind onto a Ctrl+Shift chord can ever work here.
The banner line tells you whether Textual negotiated the Kitty
keyboard protocol (which is what *would* make stacked modifiers work).

Press Ctrl+C or Ctrl+Q to quit.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual import events
from textual.widgets import RichLog, Static


class KeyProbe(App):
    CSS = "RichLog { border: round $accent; } #banner { padding: 0 1; }"

    def compose(self) -> ComposeResult:
        yield Static(id="banner")
        yield RichLog(highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        # Textual sets this when the terminal supports the Kitty keyboard
        # protocol (the thing that makes Ctrl+Shift+X distinguishable).
        supported = getattr(self, "_driver", None)
        kitty = getattr(supported, "_extended_keys", None)
        self.query_one("#banner", Static).update(
            f"[b]keyprobe[/b]  TERM={self._env_term()}  "
            f"kitty-protocol={self._kitty_state()}  "
            "— press chords; Ctrl+Q to quit"
        )
        self.query_one(RichLog).write(
            "Press: Enter / Ctrl+Enter / Ctrl+Shift+Enter / "
            "Ctrl+R / Ctrl+Shift+R / F4 / Ctrl+Shift+A"
        )

    @staticmethod
    def _env_term() -> str:
        import os

        return os.environ.get("TERM", "?")

    def _kitty_state(self) -> str:
        drv = getattr(self, "_driver", None)
        for attr in ("_extended_keys", "_kitty_protocol", "extended_keys"):
            val = getattr(drv, attr, None)
            if val is not None:
                return f"{attr}={val}"
        return "unknown (compare arrivals below)"

    def on_key(self, event: events.Key) -> None:
        if event.key in ("ctrl+q",):
            self.exit()
            return
        self.query_one(RichLog).write(
            f"[cyan]key[/]={event.key!r:28} "
            f"[green]char[/]={event.character!r:8} "
            f"[yellow]name[/]={event.name!r} "
            f"aliases={list(event.aliases)}"
        )


if __name__ == "__main__":
    KeyProbe().run()

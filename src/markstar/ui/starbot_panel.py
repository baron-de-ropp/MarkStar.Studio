"""StarBotPanel — the right-side AI chat panel (mirrors the project panel).

Owns the transcript, the input, and the two working animations (a cycling
"Thinking…" spinner and a bottom Larson scanner). It's a dumb-ish view: it posts
``Submitted`` when the user sends a message and exposes methods the app calls to
stream a reply in (add_user / start_assistant / append_assistant / add_tool /
finish_assistant). The conversation itself lives in ai/chat.StarBotChat.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Static

from markstar.ui.themes import token

_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SCAN_WIDTH = 7


class StarBotPanel(Vertical):
    DEFAULT_CSS = """
    StarBotPanel {
        dock: right;
        layer: overlay;
        width: 44;
        height: 100%;
        display: none;
        background: $boost;
        /* 3-sided box flying out from the right edge (mirror of the project
           panel): border on top/left/bottom, open on the right. */
        border-top: solid $accent 40%;
        border-left: solid $accent 40%;
        border-bottom: solid $accent 40%;
        border-title-color: $text;
        border-title-align: center;
        padding: 0 1;
    }
    StarBotPanel.visible { display: block; }

    StarBotPanel #sb-log {
        height: 1fr;
        background: $boost;
        scrollbar-size-vertical: 1;
        scrollbar-background: $boost;
        scrollbar-color: $text-muted 35%;
    }
    StarBotPanel .sb-msg { height: auto; padding: 0 0 1 0; }
    StarBotPanel #sb-spinner { height: auto; color: $text-muted; }
    StarBotPanel #sb-rule { height: 1; color: $text-muted 22%; }
    StarBotPanel #sb-input {
        border: none; padding: 0; height: auto; background: $boost;
    }
    StarBotPanel #sb-foot { height: 1; color: $text-muted; }
    """

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._assistant: Static | None = None  # the message currently streaming in
        self._assistant_text = ""
        self._spin_i = 0
        self._scan_pos = 0
        self._scan_dir = 1
        self._anim = None
        self._thinking = False

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="sb-log")
        yield Static("", id="sb-spinner")
        yield Static("─" * 40, id="sb-rule")
        yield Input(placeholder="ask StarBot…", id="sb-input")
        yield Static("", id="sb-foot")

    def on_mount(self) -> None:
        self.border_title = " StarBot "
        self._refresh_foot()
        self.query_one("#sb-spinner", Static).display = False

    # --- visibility --------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.has_class("visible")

    def open(self) -> None:
        self.add_class("visible")

    def close(self) -> None:
        self.remove_class("visible")

    def focus_input(self) -> None:
        try:
            self.query_one("#sb-input", Input).focus()
        except Exception:
            pass

    # --- transcript --------------------------------------------------------

    def _log(self) -> VerticalScroll:
        return self.query_one("#sb-log", VerticalScroll)

    def _add(self, markup: str, classes: str = "sb-msg") -> Static:
        w = Static(markup, classes=classes, markup=True)
        self._log().mount(w)
        self.call_after_refresh(lambda: self._log().scroll_end(animate=False))
        return w

    def add_user(self, text: str) -> None:
        acc = token(self, "hint-key")
        self._add(f"[{acc}]You[/]\n{_esc(text)}")

    def add_tool(self, summary: str) -> None:
        dim = token(self, "rule")
        mut = token(self, "tab-inactive")
        self._add(f"[{dim}]  · [/][{mut}]{_esc(summary)}[/]")

    def start_assistant(self) -> None:
        acc = token(self, "hint-key")
        self._assistant_text = ""
        self._assistant = self._add(f"[{acc}]StarBot[/]")
        self.set_thinking(True)

    def append_assistant(self, delta: str) -> None:
        if self._assistant is None:
            self.start_assistant()
        self._assistant_text += delta
        acc = token(self, "hint-key")
        assert self._assistant is not None
        self._assistant.update(f"[{acc}]StarBot[/]\n{_esc(self._assistant_text)}")
        self.call_after_refresh(lambda: self._log().scroll_end(animate=False))

    def finish_assistant(self) -> None:
        self.set_thinking(False)
        self._assistant = None
        self._assistant_text = ""

    # --- animations --------------------------------------------------------

    def set_thinking(self, on_: bool) -> None:
        if on_ == self._thinking:
            return
        self._thinking = on_
        spinner = self.query_one("#sb-spinner", Static)
        spinner.display = on_
        if on_:
            self._anim = self.set_interval(0.1, self._tick)
        elif self._anim is not None:
            self._anim.stop()
            self._anim = None
            spinner.update("")
        self._refresh_foot()

    def _tick(self) -> None:
        acc = token(self, "hint-key")
        mut = token(self, "tab-inactive")
        self._spin_i = (self._spin_i + 1) % len(_SPINNER)
        self.query_one("#sb-spinner", Static).update(
            f"[{acc}]{_SPINNER[self._spin_i]}[/] [{mut}]Thinking…[/]"
        )
        # Larson scanner in the footer while working.
        self._scan_pos += self._scan_dir
        if self._scan_pos >= _SCAN_WIDTH - 1 or self._scan_pos <= 0:
            self._scan_dir *= -1
        cells = "".join(
            f"[{acc}]▪[/]" if i == self._scan_pos else f"[{mut}]▫[/]"
            for i in range(_SCAN_WIDTH)
        )
        self.query_one("#sb-foot", Static).update(f"{cells}  [{mut}]working[/]")

    def _refresh_foot(self) -> None:
        if self._thinking:
            return
        acc = token(self, "hint-key")
        mut = token(self, "tab-inactive")
        self.query_one("#sb-foot", Static).update(
            f"[{acc}]Enter[/] [{mut}]send[/]   [{acc}]Ctrl+K[/] [{mut}]close[/]"
        )

    # --- input -------------------------------------------------------------

    @on(Input.Submitted, "#sb-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip()
        if not text:
            return
        inp = self.query_one("#sb-input", Input)
        inp.value = ""
        self.post_message(self.Submitted(text))


def _esc(text: str) -> str:
    return text.replace("[", "\\[")

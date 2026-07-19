"""StarBotPanel — the right-side AI chat panel (mirrors the project panel).

Owns the transcript, the input, and the two working animations (a cycling
"Thinking…" spinner and a bottom Larson scanner). It's a dumb-ish view: it posts
``Submitted`` when the user sends a message and exposes methods the app calls to
stream a reply in (add_user / start_assistant / append_assistant / add_tool /
finish_assistant). The conversation itself lives in ai/chat.StarBotChat.
"""

from __future__ import annotations

import re

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Rule, Static

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
        /* Same as the editor + project panel scrollbars (app-wide consistency). */
        scrollbar-color: $text-muted 12%;
        scrollbar-color-hover: $text-muted 45%;
        scrollbar-color-active: $text-muted 55%;
    }
    /* Body text matches the project tree's intensity ($tab-inactive) — softer
       than the editor's primary white. Name labels + tool lines set their own. */
    StarBotPanel .sb-msg { height: auto; padding: 0 0 1 0; color: $tab-inactive; }
    StarBotPanel #sb-spinner { height: auto; color: $text-muted; }
    /* A blank breathing row sits above the rule (see compose). The Rule widget
       auto-fills the panel's content width, so it always spans the chat area. */
    StarBotPanel #sb-rule {
        height: 1; margin: 0; color: $text-muted 22%; background: $boost;
    }
    StarBotPanel #sb-input {
        /* Recessed, slightly darker field so the input reads as distinct. */
        border: none; padding: 0 1; height: auto; background: $background;
        margin: 1 0;
    }
    StarBotPanel #sb-foot { height: 1; color: $text-muted; }
    /* Blank rows for breathing room below the transcript and below the hints. */
    StarBotPanel #sb-breath, StarBotPanel #sb-botpad { height: 1; }
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
        yield Static("", id="sb-breath")  # breathing row below the transcript
        yield Rule(id="sb-rule")  # auto-fills the panel width
        yield Input(placeholder="ask StarBot…", id="sb-input")
        yield Static("", id="sb-foot")
        yield Static("", id="sb-botpad")  # breathing row below the hints

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

    def clear(self) -> None:
        """Empty the transcript (new chat / before loading a saved one)."""
        self._assistant = None
        self._assistant_text = ""
        for child in list(self._log().children):
            child.remove()

    def render_messages(self, messages: list[dict]) -> None:
        """Replay a saved conversation into the transcript."""
        self.clear()
        from markstar.ai.tools import ProjectTools

        for m in messages:
            role = m.get("role")
            if role == "user":
                self.add_user(m.get("content") or "")
            elif role == "assistant":
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", {})
                    self.add_tool(
                        ProjectTools.summarize_call(
                            fn.get("name", ""), fn.get("arguments", "")
                        )
                    )
                content = (m.get("content") or "").strip()
                if content:
                    self._assistant = None
                    self.append_assistant(content)
            # system + tool-result messages aren't shown

    def add_user(self, text: str) -> None:
        self._add(f"[{self._you_color()}]You[/]\n{_esc(text)}")

    def add_tool(self, summary: str) -> None:
        dim = token(self, "rule")
        mut = token(self, "tab-inactive")
        self._add(f"[{dim}]  · [/][{mut}]{_esc(summary)}[/]")

    def _you_color(self) -> str:
        return token(self, "md-quote")   # a distinct (green-family) name color

    def _bot_color(self) -> str:
        return token(self, "hint-key")   # the accent — StarBot's brand color

    def start_assistant(self) -> None:
        self._assistant_text = ""
        self._assistant = self._add(f"[{self._bot_color()}]StarBot[/]")
        self.set_thinking(True)

    def append_assistant(self, delta: str) -> None:
        if self._assistant is None:
            self.start_assistant()
        self._assistant_text += delta
        assert self._assistant is not None
        # lstrip so a model that opens with blank lines doesn't leave a big gap
        # under the "StarBot" label.
        body = _esc(self._assistant_text.lstrip())
        self._assistant.update(f"[{self._bot_color()}]StarBot[/]\n{body}")
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


# Emoji / pictographs / variation selectors render as multi-cell (or zero-cell)
# glyphs that throw off Textual's column math — corrupting wrap width and the
# scrollbar. Strip them on the way to the screen. Arrows (→), box-drawing, and
# ordinary typography are left alone (they're single-cell and legitimate).
_EMOJI = re.compile(
    "["
    "\U0001f000-\U0001faff"  # emoji, pictographs, symbols & pictographs supplement
    "\U00002600-\U000027bf"  # miscellaneous symbols + dingbats
    "\U00002b00-\U00002bff"  # miscellaneous symbols and arrows (mostly emoji-ish)
    "\U0000fe00-\U0000fe0f"  # variation selectors (force emoji presentation)
    "\U0000200d"             # zero-width joiner (emoji sequences)
    "\U0000fe0f"
    "]"
)


def _sanitize(text: str) -> str:
    """Drop emoji (they break cell counts) and escape markup brackets."""
    return _EMOJI.sub("", text).replace("[", "\\[")


# Back-compat alias — the transcript helpers call this name.
_esc = _sanitize

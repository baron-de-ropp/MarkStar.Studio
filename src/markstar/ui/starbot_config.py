"""StarBot connection settings — Project → StarBot…

A modal form for the provider endpoint, model, and API key, with a Validate
action that runs the two-step check (connect+auth, then tool calling) and shows
the result. Save writes to the user config dir (see ai/config.py).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from markstar.ai.config import StarBotConfig
from markstar.ui.themes import token


class StarBotConfigScreen(ModalScreen[bool]):
    CSS = """
    StarBotConfigScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.55);
    }
    #sb-panel {
        width: 74;
        max-width: 90%;
        height: auto;
        background: $boost;
        border: tall $accent;
        padding: 1 2;
    }
    #sb-title { text-style: bold; color: $text; padding-bottom: 1; }
    .sb-fieldlabel { color: $text-muted; }
    #sb-panel Input { width: 100%; margin: 0 0 1 0; }
    #sb-keyhint { color: $text-muted; padding-bottom: 1; }
    #sb-results {
        height: auto;
        min-height: 3;
        color: $text-muted;
        border: round $accent 30%;
        padding: 0 1;
        margin: 1 0 0 0;
    }
    #sb-buttons { height: auto; align-horizontal: right; padding-top: 1; }
    #sb-buttons Button { margin: 0 0 0 2; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._config = StarBotConfig.load()

    def compose(self) -> ComposeResult:
        c = self._config
        with Vertical(id="sb-panel"):
            yield Label("StarBot — connection", id="sb-title")
            yield Label("Base URL", classes="sb-fieldlabel")
            yield Input(
                value=c.base_url,
                placeholder="https://api.openai.com/v1  ·  http://localhost:11434/v1",
                id="sb-base",
            )
            yield Label("Model", classes="sb-fieldlabel")
            yield Input(value=c.model, placeholder="gpt-4o-mini · llama3.1 · …", id="sb-model")
            yield Label("API key", classes="sb-fieldlabel")
            yield Input(
                value=c.api_key,
                placeholder="sk-…   or   $OPENAI_API_KEY   (read from environment)",
                password=True,
                id="sb-key",
            )
            yield Label(
                "Tip: enter $NAME to read the key from an environment variable "
                "instead of storing it.",
                id="sb-keyhint",
            )
            yield Static("Not validated yet.", id="sb-results")
            with Horizontal(id="sb-buttons"):
                yield Button("Validate", id="sb-validate")
                yield Button("Save", variant="primary", id="sb-save")
                yield Button("Cancel", id="sb-cancel")

    def on_mount(self) -> None:
        self.query_one("#sb-base", Input).focus()

    # --- current field values ------------------------------------------------

    def _current_config(self) -> StarBotConfig:
        return StarBotConfig(
            provider="openai",
            base_url=self.query_one("#sb-base", Input).value.strip(),
            model=self.query_one("#sb-model", Input).value.strip(),
            api_key=self.query_one("#sb-key", Input).value.strip(),
        )

    def _set_results(self, markup: str) -> None:
        self.query_one("#sb-results", Static).update(markup)

    # --- actions -------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sb-save":
            self._current_config().save()
            self.dismiss(True)
        elif event.button.id == "sb-cancel":
            self.dismiss(False)
        elif event.button.id == "sb-validate":
            self._validate()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _validate(self) -> None:
        cfg = self._current_config()
        if not cfg.is_configured():
            self._set_results("Enter a base URL and a model first.")
            return
        self._set_results("Validating…")
        self.run_worker(self._validate_async(cfg))

    async def _validate_async(self, cfg: StarBotConfig) -> None:
        from markstar.ai.client import OpenAIClient
        from markstar.ai.validator import validate_connection

        try:
            client = OpenAIClient(cfg)
        except Exception as exc:  # noqa: BLE001
            self._set_results(f"[{token(self, 'red')}]Client error:[/] {exc}")
            return
        report = await validate_connection(client)
        ok_c = token(self, "green")
        bad_c = token(self, "red")
        lines = []
        for step in report.steps:
            mark = f"[{ok_c}]✓[/]" if step.ok else f"[{bad_c}]✗[/]"
            lines.append(f"{mark} {step.name} — {step.detail}")
        lines.append("")
        lines.append(
            f"[{ok_c}]Ready — StarBot can connect and call tools.[/]"
            if report.ok
            else f"[{bad_c}]Not ready.[/] Fix the failing step above."
        )
        self._set_results("\n".join(lines))

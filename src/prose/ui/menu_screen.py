"""Summonable menu — OpenCode-soft list of commands for one menu or the bar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from prose.commands.registry import Command, CommandRegistry


class MenuScreen(ModalScreen[str | None]):
    """Pick a command; returns command id or None if cancelled."""

    CSS = """
    MenuScreen {
        align: center middle;
    }

    #menu-panel {
        width: 48;
        max-height: 80%;
        background: $surface;
        border: tall $accent 50%;
        padding: 1 2;
    }

    #menu-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }

    #menu-hint {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("left", "prev_menu", "Prev", show=False),
        Binding("right", "next_menu", "Next", show=False),
    ]

    def __init__(
        self,
        registry: CommandRegistry,
        menu_name: str | None = None,
    ) -> None:
        super().__init__()
        self.registry = registry
        self.menu_names = registry.menu_names()
        if menu_name and menu_name in self.menu_names:
            self.menu_index = self.menu_names.index(menu_name)
        else:
            self.menu_index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-panel"):
            yield Label("", id="menu-title")
            yield OptionList(id="menu-options")
            yield Label("Enter run · Esc close · ←/→ menus", id="menu-hint")

    def on_mount(self) -> None:
        self._reload_options()
        self.query_one("#menu-options", OptionList).focus()

    def _current_menu(self) -> str:
        return self.menu_names[self.menu_index]

    def _commands(self) -> list[Command]:
        return self.registry.menus().get(self._current_menu(), [])

    def _reload_options(self) -> None:
        title = self.query_one("#menu-title", Label)
        bar = "  ".join(
            f"[bold]{n}[/]" if n == self._current_menu() else n for n in self.menu_names
        )
        title.update(f"{bar}")

        options = self.query_one("#menu-options", OptionList)
        options.clear_options()
        for cmd in self._commands():
            shortcut = f"  {cmd.binding}" if cmd.binding else ""
            disabled = not cmd.is_enabled()
            # Pad label so shortcuts align loosely on the right
            label = f"{cmd.label:<28}{shortcut}"
            options.add_option(Option(label, id=cmd.id, disabled=disabled))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id
        if opt_id:
            self.dismiss(str(opt_id))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_prev_menu(self) -> None:
        if not self.menu_names:
            return
        self.menu_index = (self.menu_index - 1) % len(self.menu_names)
        self._reload_options()

    def action_next_menu(self) -> None:
        if not self.menu_names:
            return
        self.menu_index = (self.menu_index + 1) % len(self.menu_names)
        self._reload_options()

"""Classic menu ribbon — top bar of menu names + dropdown list of commands."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from prose.commands.registry import Command, CommandRegistry


class MenuScreen(ModalScreen[str | None]):
    """Word/Works-style ribbon: File Edit View… across the top, items drop below."""

    CSS = """
    MenuScreen {
        align: left top;
        background: $background 40%;
    }

    #ribbon {
        width: 100%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border-bottom: tall $accent 50%;
        padding: 0 1 1 1;
    }

    #menu-bar {
        width: 100%;
        height: 1;
        padding: 0 1;
        text-style: bold;
        color: $text-muted;
    }

    #menu-bar .active-menu {
        color: $text;
        text-style: bold reverse;
    }

    #menu-options {
        width: 100%;
        max-height: 20;
        margin-top: 0;
        border: tall $accent 30%;
        background: $surface;
    }

    #menu-hint {
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("left", "prev_menu", "Prev", show=False),
        Binding("right", "next_menu", "Next", show=False),
        # letter jump within open ribbon (first letter of menu name)
        Binding("f", "jump_file", show=False),
        Binding("e", "jump_edit", show=False),
        Binding("v", "jump_view", show=False),
        Binding("h", "jump_help", show=False),
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
        with Vertical(id="ribbon"):
            yield Static("", id="menu-bar")
            yield OptionList(id="menu-options")
            yield Label(
                "←/→ menus  ·  Enter run  ·  Esc close  ·  F/E/V/H jump",
                id="menu-hint",
            )

    def on_mount(self) -> None:
        self._reload_options()
        self.query_one("#menu-options", OptionList).focus()

    def _current_menu(self) -> str:
        if not self.menu_names:
            return ""
        return self.menu_names[self.menu_index]

    def _commands(self) -> list[Command]:
        return self.registry.menus().get(self._current_menu(), [])

    def _reload_options(self) -> None:
        # Ribbon titles: highlight active like a classic menu bar
        parts: list[str] = []
        for name in self.menu_names:
            if name == self._current_menu():
                parts.append(f"[bold reverse] {name} [/]")
            else:
                parts.append(f" {name} ")
        self.query_one("#menu-bar", Static).update("".join(parts))

        options = self.query_one("#menu-options", OptionList)
        options.clear_options()
        for cmd in self._commands():
            shortcut = ""
            if cmd.binding:
                # Humanize a bit for the ribbon
                shortcut = cmd.binding.replace("ctrl+", "Ctrl+").replace("shift+", "Shift+")
                shortcut = f"  {shortcut}"
            disabled = not cmd.is_enabled()
            label = f"  {cmd.label:<26}{shortcut}"
            options.add_option(Option(label, id=cmd.id, disabled=disabled))
        if options.option_count:
            options.highlighted = 0

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

    def action_jump_file(self) -> None:
        self._jump("File")

    def action_jump_edit(self) -> None:
        self._jump("Edit")

    def action_jump_view(self) -> None:
        self._jump("View")

    def action_jump_help(self) -> None:
        self._jump("Help")

    def _jump(self, name: str) -> None:
        if name in self.menu_names:
            self.menu_index = self.menu_names.index(name)
            self._reload_options()

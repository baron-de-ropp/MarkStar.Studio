"""In-layout classic menu ribbon — top terminal line + dropdown list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from markstar.commands.registry import Command, CommandRegistry


class MenuBar(Vertical):
    """Word/Works-style ribbon fixed to the first line of the app layout.

    Hidden until opened (Esc / F9). Line 1 is menu names; a dropdown of
    commands sits directly under it and pushes content down (no modal overlay).
    """

    DEFAULT_CSS = """
    MenuBar {
        width: 100%;
        height: auto;
        display: none;
        background: $boost;
        layer: above;
    }

    MenuBar.open {
        display: block;
    }

    MenuBar #menu-names {
        width: 100%;
        height: 1;
        padding: 0 1;
        color: $text;
        text-style: bold;
        background: $accent 30%;
    }

    MenuBar #menu-options {
        width: auto;
        min-width: 36;
        max-width: 72;
        height: auto;
        max-height: 16;
        margin: 0 0 0 1;
        border: solid $accent 50%;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False, priority=True),
        Binding("f9", "close", "Close", show=False, priority=True),
        Binding("left", "prev_menu", "Prev", show=False, priority=True),
        Binding("right", "next_menu", "Next", show=False, priority=True),
        Binding("f", "jump_file", show=False, priority=True),
        Binding("e", "jump_edit", show=False, priority=True),
        Binding("v", "jump_view", show=False, priority=True),
        Binding("h", "jump_help", show=False, priority=True),
    ]

    class CommandChosen(Message):
        """User picked a command from the open menu."""

        def __init__(self, command_id: str) -> None:
            super().__init__()
            self.command_id = command_id

    class Closed(Message):
        """Menu dismissed without a command (or after run)."""

    def __init__(self, registry: CommandRegistry, **kwargs) -> None:
        super().__init__(**kwargs)
        self.registry = registry
        self.menu_names: list[str] = []
        self.menu_index = 0
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def compose(self) -> ComposeResult:
        yield Static("", id="menu-names")
        yield OptionList(id="menu-options")

    def open_menu(self, menu_name: str | None = None) -> None:
        """Show the ribbon on the top line and focus the dropdown."""
        self.menu_names = list(self.registry.menu_names())
        if menu_name and menu_name in self.menu_names:
            self.menu_index = self.menu_names.index(menu_name)
        else:
            self.menu_index = 0
        self._open = True
        self.add_class("open")
        self._reload()
        self.call_after_refresh(self._focus_options)

    def close_menu(self, *, notify: bool = True) -> None:
        """Hide the ribbon and optionally post Closed."""
        if not self._open:
            return
        self._open = False
        self.remove_class("open")
        if notify:
            self.post_message(self.Closed())

    def action_close(self) -> None:
        self.close_menu()

    def action_prev_menu(self) -> None:
        if not self.menu_names:
            return
        self.menu_index = (self.menu_index - 1) % len(self.menu_names)
        self._reload()

    def action_next_menu(self) -> None:
        if not self.menu_names:
            return
        self.menu_index = (self.menu_index + 1) % len(self.menu_names)
        self._reload()

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
            self._reload()

    def _current_menu(self) -> str:
        if not self.menu_names:
            return ""
        return self.menu_names[self.menu_index]

    def _commands(self) -> list[Command]:
        name = self._current_menu()
        if not name:
            return []
        return list(self.registry.menus().get(name, []))

    def _focus_options(self) -> None:
        try:
            self.query_one("#menu-options", OptionList).focus()
        except Exception:
            pass

    def _reload(self) -> None:
        try:
            bar = self.query_one("#menu-names", Static)
            options = self.query_one("#menu-options", OptionList)
        except Exception:
            self.call_after_refresh(self._reload)
            return

        parts: list[str] = []
        for name in self.menu_names:
            if name == self._current_menu():
                parts.append(f"[bold reverse] {name} [/]")
            else:
                parts.append(f" {name} ")
        bar.update("".join(parts) if parts else " (no menus) ")

        options.clear_options()
        cmds = self._commands()
        if not cmds:
            options.add_option(Option("  (empty menu)", id="_empty", disabled=True))
            return
        for cmd in cmds:
            shortcut = ""
            if cmd.binding:
                shortcut = (
                    cmd.binding.replace("ctrl+", "Ctrl+")
                    .replace("shift+", "Shift+")
                    .replace("alt+", "Alt+")
                    .replace("pagedown", "PgDn")
                    .replace("pageup", "PgUp")
                    .replace("full_stop", ".")
                    .replace("comma", ",")
                )
                # Uppercase bare function keys (e.g. "f7" -> "F7").
                if shortcut and shortcut[0] == "f" and shortcut[1:].isdigit():
                    shortcut = shortcut.upper()
                shortcut = f"   {shortcut}"
            disabled = not cmd.is_enabled()
            # Toggle commands carry a leading ✓/space marker; the column is
            # reserved for every row so labels stay aligned down the menu.
            state = cmd.is_checked()
            mark = ("✓ " if state else "  ") if state is not None else "  "
            label = f"  {mark}{cmd.label:<28}{shortcut}"
            options.add_option(Option(label, id=cmd.id, disabled=disabled))
        if options.option_count > 0:
            options.highlighted = 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id
        if opt_id and opt_id != "_empty":
            self.close_menu(notify=False)
            self.post_message(self.CommandChosen(str(opt_id)))
            self.post_message(self.Closed())

"""Command registry — menus and keybindings share one catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional


EnabledFn = Callable[[], bool]
HandlerFn = Callable[[], None]


@dataclass
class Command:
    """One user-facing action (menu row + optional keybinding)."""

    id: str
    label: str
    menu: str
    binding: Optional[str] = None  # Textual key syntax, e.g. "ctrl+s"
    handler: Optional[HandlerFn] = None
    enabled: Optional[EnabledFn] = None
    show_in_footer: bool = False

    def is_enabled(self) -> bool:
        if self.enabled is None:
            return True
        return bool(self.enabled())


@dataclass
class CommandRegistry:
    """Maps command ids to handlers; drives menus and keybindings."""

    _commands: dict[str, Command] = field(default_factory=dict)

    def register(self, command: Command) -> None:
        if command.id in self._commands:
            raise ValueError(f"duplicate command id: {command.id}")
        self._commands[command.id] = command

    def get(self, command_id: str) -> Command:
        try:
            return self._commands[command_id]
        except KeyError as exc:
            raise KeyError(f"unknown command: {command_id}") from exc

    def __contains__(self, command_id: str) -> bool:
        return command_id in self._commands

    def __iter__(self) -> Iterable[Command]:
        return iter(self._commands.values())

    def execute(self, command_id: str) -> bool:
        """Run command if enabled. Returns False if disabled or missing handler."""
        cmd = self.get(command_id)
        if not cmd.is_enabled():
            return False
        if cmd.handler is None:
            return False
        cmd.handler()
        return True

    def menus(self) -> dict[str, list[Command]]:
        """Commands grouped by menu name, registration order within each menu."""
        grouped: dict[str, list[Command]] = {}
        for cmd in self._commands.values():
            grouped.setdefault(cmd.menu, []).append(cmd)
        return grouped

    def menu_names(self) -> list[str]:
        """Stable menu order for the bar."""
        order = ["File", "Edit", "View", "Insert", "Format", "Tools", "Project", "Help"]
        present = self.menus()
        names = [n for n in order if n in present]
        for name in present:
            if name not in names:
                names.append(name)
        return names

    def bindings(self) -> list[tuple[str, str, str]]:
        """List of (textual_key, command_id, label) for commands with bindings."""
        out: list[tuple[str, str, str]] = []
        for cmd in self._commands.values():
            if cmd.binding:
                out.append((cmd.binding, cmd.id, cmd.label))
        return out

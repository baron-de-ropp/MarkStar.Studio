"""Unit tests for CommandRegistry."""

from __future__ import annotations

import pytest

from prose.commands.registry import Command, CommandRegistry


def test_register_and_get() -> None:
    reg = CommandRegistry()
    reg.register(Command(id="save", label="Save", menu="File", binding="ctrl+s"))
    assert reg.get("save").label == "Save"
    assert "save" in reg


def test_duplicate_id_raises() -> None:
    reg = CommandRegistry()
    reg.register(Command(id="save", label="Save", menu="File"))
    with pytest.raises(ValueError, match="duplicate"):
        reg.register(Command(id="save", label="Save again", menu="File"))


def test_execute_runs_handler() -> None:
    reg = CommandRegistry()
    called: list[str] = []
    reg.register(
        Command(
            id="save",
            label="Save",
            menu="File",
            handler=lambda: called.append("ok"),
        )
    )
    assert reg.execute("save") is True
    assert called == ["ok"]


def test_execute_disabled_returns_false() -> None:
    reg = CommandRegistry()
    called = False

    def handler() -> None:
        nonlocal called
        called = True

    reg.register(
        Command(
            id="redo",
            label="Redo",
            menu="Edit",
            handler=handler,
            enabled=lambda: False,
        )
    )
    assert reg.execute("redo") is False
    assert called is False


def test_menus_group_commands() -> None:
    reg = CommandRegistry()
    reg.register(Command(id="save", label="Save", menu="File"))
    reg.register(Command(id="undo", label="Undo", menu="Edit"))
    reg.register(Command(id="quit", label="Exit", menu="File"))
    menus = reg.menus()
    assert [c.id for c in menus["File"]] == ["save", "quit"]
    assert [c.id for c in menus["Edit"]] == ["undo"]


def test_menu_names_stable_order() -> None:
    reg = CommandRegistry()
    reg.register(Command(id="a", label="A", menu="Help"))
    reg.register(Command(id="b", label="B", menu="File"))
    assert reg.menu_names() == ["File", "Help"]


def test_bindings_lists_only_bound_commands() -> None:
    reg = CommandRegistry()
    reg.register(Command(id="save", label="Save", menu="File", binding="ctrl+s"))
    reg.register(Command(id="about", label="About", menu="Help"))
    assert reg.bindings() == [("ctrl+s", "save", "Save")]


def test_unknown_command_raises() -> None:
    reg = CommandRegistry()
    with pytest.raises(KeyError, match="unknown"):
        reg.get("nope")

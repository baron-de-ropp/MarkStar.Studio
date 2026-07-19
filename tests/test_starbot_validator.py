"""validate_connection: two-step check driven with a stub client (no network)."""

from __future__ import annotations

import asyncio

from markstar.ai.client import CompletionResult, ToolCall
from markstar.ai.validator import validate_connection


def _run(coro):
    return asyncio.run(coro)


class _StubClient:
    """Returns scripted results in order; an entry may be an Exception to raise."""

    def __init__(self, *script):
        self._script = list(script)
        self.calls: list[tuple] = []

    async def complete(self, messages, tools=None):
        self.calls.append((messages, tools))
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _echo_call():
    return CompletionResult("", [ToolCall("1", "echo", '{"text":"ping"}')])


def test_all_pass() -> None:
    client = _StubClient(CompletionResult("OK"), _echo_call())
    report = _run(validate_connection(client))
    assert report.ok is True
    assert [s.ok for s in report.steps] == [True, True]
    assert len(client.calls) == 2  # auth, then tools
    # The tool step actually passed a tool definition.
    assert client.calls[1][1] and client.calls[1][1][0]["function"]["name"] == "echo"


def test_auth_failure_short_circuits() -> None:
    client = _StubClient(RuntimeError("401 Unauthorized"))
    report = _run(validate_connection(client))
    assert report.ok is False
    assert len(report.steps) == 1  # tool step never attempted
    assert "401" in report.steps[0].detail


def test_connects_but_no_tool_support() -> None:
    client = _StubClient(CompletionResult("OK"), CompletionResult("I cannot do that."))
    report = _run(validate_connection(client))
    assert report.ok is False
    assert report.steps[0].ok is True
    assert report.steps[1].ok is False
    assert "not call the tool" in report.steps[1].detail


def test_tool_step_error_is_reported() -> None:
    client = _StubClient(CompletionResult("OK"), RuntimeError("boom"))
    report = _run(validate_connection(client))
    assert report.ok is False
    assert report.steps[1].ok is False
    assert "boom" in report.steps[1].detail

"""StarBotChat agentic loop, driven with a stub streaming client."""

from __future__ import annotations

import asyncio

from markstar.ai.chat import StarBotChat
from markstar.ai.client import ToolCall


def _run(coro):
    return asyncio.run(coro)


class _StubClient:
    """Each stream() call replays the next scripted list of events."""

    def __init__(self, *turns):
        self._turns = list(turns)
        self.seen_tools = []

    async def stream(self, messages, tools=None):
        self.seen_tools.append(tools)
        for event in self._turns.pop(0):
            yield event


class _StubTools:
    def __init__(self, result="TOOL RESULT"):
        self.result = result
        self.calls = []

    def execute(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


def _collect():
    events = []
    return events, (lambda e: events.append(e))


def test_plain_reply_streams_text_and_finishes() -> None:
    client = _StubClient([("text", "Hello"), ("text", " there")])
    chat = StarBotChat(client, tools=None)
    events, emit = _collect()
    _run(chat.send("hi", emit))
    assert ("text", "Hello") in events and ("text", " there") in events
    assert events[-1] == ("done", None)
    # History: system, user, assistant.
    assert chat.messages[-1] == {"role": "assistant", "content": "Hello there"}
    assert chat.messages[1] == {"role": "user", "content": "hi"}


def test_tool_round_executes_then_continues() -> None:
    call = ToolCall("call_1", "grep", '{"pattern": "sigil"}')
    client = _StubClient(
        [("tool_calls", [call])],          # round 1: model asks to grep
        [("text", "Found 2 matches.")],    # round 2: final answer
    )
    tools = _StubTools("book/ch-01.md:1: The sigil…")
    chat = StarBotChat(client, tools=tools)
    events, emit = _collect()
    _run(chat.send("check sigils", emit))

    assert ("tool", 'grep "sigil"') in events        # activity line
    assert ("text", "Found 2 matches.") in events
    assert events[-1] == ("done", None)
    assert tools.calls == [("grep", '{"pattern": "sigil"}')]
    # A tool-result message was inserted before the final assistant turn.
    roles = [m["role"] for m in chat.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    assert chat.messages[3]["content"] == "book/ch-01.md:1: The sigil…"


def test_tools_advertised_only_when_present() -> None:
    with_tools = _StubClient([("text", "ok")])
    StarBotChat(with_tools, tools=_StubTools())
    _run(StarBotChat(with_tools, tools=_StubTools()).send("x", _collect()[1]))
    assert with_tools.seen_tools[0] is not None  # tool specs passed

    no_tools = _StubClient([("text", "ok")])
    _run(StarBotChat(no_tools, tools=None).send("x", _collect()[1]))
    assert no_tools.seen_tools[0] is None

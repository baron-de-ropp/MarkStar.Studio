"""Validate a StarBot connection before we rely on it.

Two checks, because a connection that *chats* isn't enough — the whole assistant
depends on tool calling, and plenty of models/endpoints don't support it:

1. Connect + auth — a minimal completion round-trips (endpoint reachable, key
   accepted, model name valid).
2. Tool calling — given a dummy ``echo`` tool and a prompt that should trigger
   it, the model actually returns a tool call.

Pure coordination over a ``StarBotClient``, so it's testable with a stub.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from markstar.ai.client import StarBotClient

# A trivial tool the validator asks the model to call.
_ECHO_TOOL = {
    "type": "function",
    "function": {
        "name": "echo",
        "description": "Echo the given text back to the caller.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
}


@dataclass
class Step:
    name: str
    ok: bool
    detail: str


@dataclass
class ValidationReport:
    ok: bool
    steps: list[Step] = field(default_factory=list)


async def validate_connection(client: StarBotClient) -> ValidationReport:
    steps: list[Step] = []

    # 1) Connect + auth.
    try:
        await client.complete([{"role": "user", "content": "Reply with the word OK."}])
        steps.append(Step("Connect + auth", True, "the model responded"))
    except Exception as exc:  # noqa: BLE001 — surface any failure to the user
        steps.append(Step("Connect + auth", False, _brief(exc)))
        return ValidationReport(False, steps)  # no point testing tools if unreachable

    # 2) Tool calling.
    try:
        result = await client.complete(
            [
                {
                    "role": "user",
                    "content": "Call the echo tool with the text 'ping'.",
                }
            ],
            tools=[_ECHO_TOOL],
        )
        if any(c.name == "echo" for c in result.tool_calls):
            steps.append(Step("Tool calling", True, "the model issued a tool call"))
        else:
            steps.append(
                Step(
                    "Tool calling",
                    False,
                    "the model replied but did not call the tool — "
                    "this model/endpoint may not support tools",
                )
            )
    except Exception as exc:  # noqa: BLE001
        steps.append(Step("Tool calling", False, _brief(exc)))

    return ValidationReport(all(s.ok for s in steps), steps)


def _brief(exc: Exception) -> str:
    msg = str(exc).strip() or exc.__class__.__name__
    return msg if len(msg) <= 200 else msg[:197] + "…"

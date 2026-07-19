"""StarBot chat client — a thin, provider-neutral wrapper over the model API.

``StarBotClient`` is the interface the rest of the app talks to; ``OpenAIClient``
implements it against any OpenAI-compatible Chat Completions endpoint (OpenAI,
OpenRouter, Groq, Together, a local Ollama/LM Studio/vLLM, …) via the ``openai``
SDK. The SDK is imported lazily so the rest of the app — and the test suite —
never depends on it unless a real connection is actually made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, as returned by the model


@dataclass
class CompletionResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class StarBotClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> CompletionResult: ...

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Yield ("text", delta) events as they arrive, then a final
        ("tool_calls", list[ToolCall]) if the model requested any."""
        ...


class OpenAIClient:
    """OpenAI-compatible implementation. ``base_url`` points it anywhere."""

    def __init__(self, config) -> None:
        from openai import AsyncOpenAI  # lazy: only when a real client is built

        self._model = config.model
        self._client = AsyncOpenAI(
            base_url=config.base_url or None,
            # Many local endpoints ignore the key but the SDK requires a non-empty
            # string; fall back to a placeholder when none is configured.
            api_key=config.resolve_key() or "not-needed",
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> CompletionResult:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools or None,
        )
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for tc in getattr(msg, "tool_calls", None) or []:
            calls.append(
                ToolCall(
                    id=getattr(tc, "id", "") or "",
                    name=tc.function.name,
                    arguments=tc.function.arguments or "",
                )
            )
        return CompletionResult(text=msg.content or "", tool_calls=calls)

    async def stream(self, messages, tools=None):
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools or None,
            stream=True,
        )
        # Tool-call fragments arrive split across chunks, keyed by index.
        acc: dict[int, dict[str, str]] = {}
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                yield ("text", delta.content)
            for tc in getattr(delta, "tool_calls", None) or []:
                entry = acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    entry["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn and getattr(fn, "name", None):
                    entry["name"] = fn.name
                if fn and getattr(fn, "arguments", None):
                    entry["arguments"] += fn.arguments
        if acc:
            calls = [
                ToolCall(e["id"], e["name"], e["arguments"])
                for e in acc.values()
                if e["name"]
            ]
            if calls:
                yield ("tool_calls", calls)

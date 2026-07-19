"""StarBot chat client — a thin, provider-neutral wrapper over the model API.

``StarBotClient`` is the interface the rest of the app talks to; ``OpenAIClient``
implements it against any OpenAI-compatible Chat Completions endpoint (OpenAI,
OpenRouter, Groq, Together, a local Ollama/LM Studio/vLLM, …) via the ``openai``
SDK. The SDK is imported lazily so the rest of the app — and the test suite —
never depends on it unless a real connection is actually made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


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
    """Minimal surface: one non-streaming completion. (Streaming + the agentic
    loop arrive in Phase 2; the validator only needs this.)"""

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> CompletionResult: ...


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

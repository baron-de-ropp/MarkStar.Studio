"""StarBotChat — the conversation + agentic tool loop.

Holds the message history and, on each user turn, streams a reply from the
client; if the model asks to call tools, it runs them (read-only project tools),
feeds the results back, and continues until the model produces a final answer.
Everything the UI needs is delivered through an ``emit`` callback, so the loop
itself is UI-free and testable with a stub client.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

SYSTEM_PROMPT = (
    "You are StarBot, an expert editorial assistant embedded in MarkStar, a "
    "terminal writing app. The writer is working on a project — typically a "
    "multi-book novel series in Markdown files. You help with developmental, "
    "line, copy, and proofreading editing.\n\n"
    "You have READ-ONLY tools to explore the project: list_files, grep, and "
    "read_file. Use them to ground every observation in the actual text — quote "
    "specific passages and cite file:line. For continuity and consistency work "
    "(names, places, established facts, timelines), grep is your best friend.\n\n"
    "You cannot edit files yet, so give precise, actionable notes rather than "
    "rewrites. Be concise, concrete, and honest; respect the writer's voice.\n\n"
    "Do NOT use emoji or other decorative multi-cell Unicode characters — the "
    "terminal renders them at the wrong width and it breaks the layout. Plain "
    "text and standard punctuation only."
)

# Event kinds passed to emit():
#   ("text", str)        streamed assistant text delta
#   ("tool", str)        a one-line summary of a tool call being run
#   ("done", None)       the turn is complete
Emit = Callable[[tuple[str, Any]], None]


class StarBotChat:
    def __init__(
        self,
        client,
        tools=None,
        system_prompt: str = SYSTEM_PROMPT,
        max_tool_rounds: int = 8,
    ) -> None:
        self._client = client
        self._tools = tools
        self._max_rounds = max_tool_rounds
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._messages

    def restore(self, messages: list[dict[str, Any]]) -> None:
        """Replace the conversation history (loading a saved transcript)."""
        self._messages = list(messages)

    def _tool_specs(self) -> Optional[list[dict[str, Any]]]:
        if self._tools is None:
            return None
        from markstar.ai.tools import TOOL_SPECS

        return TOOL_SPECS

    async def send(self, user_text: str, emit: Emit) -> None:
        """Run one user turn to completion (through any tool rounds)."""
        self._messages.append({"role": "user", "content": user_text})
        for _ in range(self._max_rounds):
            text = ""
            tool_calls = []
            async for kind, payload in self._client.stream(
                self._messages, self._tool_specs()
            ):
                if kind == "text":
                    text += payload
                    emit(("text", payload))
                elif kind == "tool_calls":
                    tool_calls = payload

            assistant: dict[str, Any] = {"role": "assistant", "content": text or None}
            if tool_calls:
                assistant["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": c.arguments},
                    }
                    for c in tool_calls
                ]
            self._messages.append(assistant)

            if not tool_calls:
                emit(("done", None))
                return

            for c in tool_calls:
                from markstar.ai.tools import ProjectTools

                emit(("tool", ProjectTools.summarize_call(c.name, c.arguments)))
                result = (
                    self._tools.execute(c.name, c.arguments)
                    if self._tools is not None
                    else "(no tools available)"
                )
                self._messages.append(
                    {"role": "tool", "tool_call_id": c.id, "content": result}
                )

        emit(("done", None))  # hit the tool-round ceiling

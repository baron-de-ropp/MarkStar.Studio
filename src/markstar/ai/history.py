"""Per-project chat history — one JSON transcript per conversation.

Transcripts live in ``<project>/.starbot_chat_history/<id>.json`` so a novel's
editorial conversations travel with the novel. The store is pure file I/O (the
timestamped id is supplied by the caller, keeping it deterministic in tests).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DIRNAME = ".starbot_chat_history"


@dataclass
class ChatTranscript:
    id: str                                  # e.g. "2026-07-19T14-30-05"
    created: str = ""                        # ISO timestamp
    messages: list[dict] = field(default_factory=list)

    @property
    def title(self) -> str:
        """A short label — the first user message, for the history list."""
        for m in self.messages:
            if m.get("role") == "user":
                t = " ".join((m.get("content") or "").split())
                return (t[:57] + "…") if len(t) > 58 else (t or "(empty)")
        return "(empty)"

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.messages if m.get("role") == "user")

    def to_dict(self) -> dict:
        return {"id": self.id, "created": self.created, "messages": self.messages}

    @classmethod
    def from_dict(cls, d: dict) -> "ChatTranscript":
        return cls(
            id=str(d.get("id", "")),
            created=str(d.get("created", "")),
            messages=list(d.get("messages", [])),
        )


class ChatStore:
    def __init__(self, project_root: Path) -> None:
        self._dir = Path(project_root) / DIRNAME

    @property
    def directory(self) -> Path:
        return self._dir

    def path(self, transcript_id: str) -> Path:
        return self._dir / f"{_safe(transcript_id)}.json"

    def save(self, transcript: ChatTranscript) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self.path(transcript.id).write_text(
                json.dumps(transcript.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass  # never let a history write take down the editor

    def load(self, transcript_id: str) -> ChatTranscript | None:
        try:
            data = json.loads(self.path(transcript_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return ChatTranscript.from_dict(data)

    def list(self) -> list[ChatTranscript]:
        """All transcripts, newest first (by created, then id)."""
        out: list[ChatTranscript] = []
        try:
            files = list(self._dir.glob("*.json"))
        except OSError:
            return out
        for p in files:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append(ChatTranscript.from_dict(data))
        out.sort(key=lambda t: (t.created, t.id), reverse=True)
        return out

    def delete(self, transcript_id: str) -> None:
        try:
            self.path(transcript_id).unlink()
        except OSError:
            pass


def _safe(transcript_id: str) -> str:
    """Keep the id filesystem-safe (it's a timestamp, but be defensive)."""
    return "".join(c if (c.isalnum() or c in "-_.T:") else "_" for c in transcript_id) or "chat"

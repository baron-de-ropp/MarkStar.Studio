"""StarBot connection config — provider endpoint, model, and API key.

Stored in the user config dir (NOT the project folder — a project may be a git
repo you'd commit), file perms 0600. The key field may hold a literal key or a
reference to an environment variable (``$NAME`` or ``env:NAME``) so secrets need
never be written to disk at all.

Set ``STARBOT_CONFIG`` to override the path (used by tests so they never touch a
real user config).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass

from markstar.config import config_dir


def config_path():
    override = os.environ.get("STARBOT_CONFIG")
    from pathlib import Path

    return Path(override) if override else config_dir() / "starbot.toml"


@dataclass
class StarBotConfig:
    """A single StarBot provider profile."""

    provider: str = "openai"  # OpenAI-compatible Chat Completions (the only kind for now)
    base_url: str = ""        # e.g. https://api.openai.com/v1  or  http://localhost:11434/v1
    model: str = ""           # e.g. gpt-4o-mini, claude-…, llama3.1, …
    api_key: str = ""         # a literal key, or "$ENV_NAME" / "env:ENV_NAME" to read one

    def resolve_key(self) -> str:
        """The effective key — resolving a ``$NAME`` / ``env:NAME`` reference."""
        k = (self.api_key or "").strip()
        if k.startswith("$"):
            return os.environ.get(k[1:], "")
        if k.startswith("env:"):
            return os.environ.get(k[4:], "")
        return k

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    @classmethod
    def load(cls) -> "StarBotConfig":
        cfg = cls()
        try:
            with open(config_path(), "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return cfg  # missing / unreadable / malformed → defaults
        for field_name in ("provider", "base_url", "model", "api_key"):
            value = data.get(field_name)
            if isinstance(value, str):
                setattr(cfg, field_name, value)
        return cfg

    def save(self) -> None:
        path = config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._to_toml(), encoding="utf-8")
            # Best-effort tighten perms (POSIX only) — the key may be a secret.
            try:
                os.chmod(path, 0o600)
            except (OSError, NotImplementedError):
                pass
        except OSError:
            pass  # never let a config write take down the editor

    def _to_toml(self) -> str:
        def esc(v: str) -> str:
            return v.replace("\\", "\\\\").replace('"', '\\"')

        lines = [
            "# StarBot connection — safe to hand-edit.",
            "# api_key may be a literal, or \"$ENV_NAME\" to read from the environment.",
            "",
            f'provider = "{esc(self.provider)}"',
            f'base_url = "{esc(self.base_url)}"',
            f'model = "{esc(self.model)}"',
            f'api_key = "{esc(self.api_key)}"',
        ]
        return "\n".join(lines) + "\n"

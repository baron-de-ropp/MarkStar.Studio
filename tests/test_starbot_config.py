"""StarBotConfig: round-trip, key resolution, env override."""

from __future__ import annotations

import os

from markstar.ai.config import StarBotConfig, config_path


def test_config_path_honors_env_override(tmp_path, monkeypatch) -> None:
    target = tmp_path / "sb.toml"
    monkeypatch.setenv("STARBOT_CONFIG", str(target))
    assert config_path() == target


def test_save_and_reload_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STARBOT_CONFIG", str(tmp_path / "sb.toml"))
    StarBotConfig(
        base_url="http://localhost:11434/v1", model="llama3.1", api_key="secret"
    ).save()
    reloaded = StarBotConfig.load()
    assert reloaded.base_url == "http://localhost:11434/v1"
    assert reloaded.model == "llama3.1"
    assert reloaded.api_key == "secret"


def test_missing_config_returns_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STARBOT_CONFIG", str(tmp_path / "none.toml"))
    cfg = StarBotConfig.load()
    assert cfg.provider == "openai" and cfg.base_url == "" and cfg.model == ""


def test_resolve_key_literal_and_env(monkeypatch) -> None:
    assert StarBotConfig(api_key="sk-literal").resolve_key() == "sk-literal"
    monkeypatch.setenv("MY_KEY", "from-env")
    assert StarBotConfig(api_key="$MY_KEY").resolve_key() == "from-env"
    assert StarBotConfig(api_key="env:MY_KEY").resolve_key() == "from-env"
    # Unset env var resolves to empty, not the literal reference.
    monkeypatch.delenv("MY_KEY", raising=False)
    assert StarBotConfig(api_key="$MY_KEY").resolve_key() == ""


def test_is_configured_needs_base_url_and_model() -> None:
    assert StarBotConfig().is_configured() is False
    assert StarBotConfig(base_url="x").is_configured() is False
    assert StarBotConfig(base_url="x", model="m").is_configured() is True


def test_saved_file_permissions_are_tight(tmp_path, monkeypatch) -> None:
    path = tmp_path / "sb.toml"
    monkeypatch.setenv("STARBOT_CONFIG", str(path))
    StarBotConfig(base_url="x", model="m", api_key="sk").save()
    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600  # not world/group readable — it may hold a secret

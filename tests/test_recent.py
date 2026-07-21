"""Recent-items list algebra and the display helpers behind the welcome rows."""

from __future__ import annotations

from pathlib import Path

from markstar.domain.recent import (
    abbreviate_dir,
    prune_missing,
    push_recent,
    relative_age,
)


def test_push_puts_newest_first(tmp_path: Path) -> None:
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    items = push_recent([], a, 5)
    items = push_recent(items, b, 5)
    assert items[0] == str(b.resolve())


def test_push_dedupes_on_reopen(tmp_path: Path) -> None:
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    items = push_recent(push_recent([], a, 5), b, 5)
    items = push_recent(items, a, 5)
    assert items == [str(a.resolve()), str(b.resolve())]


def test_push_caps_the_list(tmp_path: Path) -> None:
    items: list[str] = []
    for i in range(10):
        items = push_recent(items, tmp_path / f"f{i}.md", 3)
    assert len(items) == 3


def test_push_collapses_equivalent_spellings(tmp_path: Path, monkeypatch) -> None:
    """./ch.md and the absolute path are the same file, so one entry."""
    target = tmp_path / "ch.md"
    target.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    items = push_recent([], target, 5)
    items = push_recent(items, Path("ch.md"), 5)
    assert len(items) == 1


def test_prune_drops_missing_and_directories(tmp_path: Path) -> None:
    real = tmp_path / "here.md"
    real.write_text("x", encoding="utf-8")
    folder = tmp_path / "adir"
    folder.mkdir()
    kept = prune_missing([str(real), str(tmp_path / "gone.md"), str(folder)])
    assert kept == [str(real)]


def test_relative_age_buckets() -> None:
    now = 1_000_000.0
    assert relative_age(now - 10, now) == "just now"
    assert relative_age(now - 300, now) == "5m ago"
    assert relative_age(now - 3 * 3600, now) == "3h ago"
    assert relative_age(now - 2 * 86400, now) == "2d ago"
    assert relative_age(now - 14 * 86400, now) == "2w ago"


def test_relative_age_survives_future_timestamps() -> None:
    now = 1_000_000.0
    assert relative_age(now + 500, now) == "just now"


def test_abbreviate_dir_uses_tilde(tmp_path: Path) -> None:
    out = abbreviate_dir(tmp_path / "books", home=tmp_path)
    assert out == "~/books"


def test_abbreviate_dir_elides_the_middle() -> None:
    long = "/a/very/long/path/that/keeps/going/and/going/for/ages/indeed"
    out = abbreviate_dir(long, home=Path("/nowhere"), width=20)
    assert len(out) <= 20
    assert "…" in out
    assert out.startswith("/a/")       # head kept
    assert out.endswith("indeed")      # tail kept

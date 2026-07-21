"""Export: HTML always works, pandoc formats degrade with a usable message."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from markstar.domain import export

MD = "# Chapter One\n\nThe warden **sleeps** and *waits*.\n\n- a torch\n"


def test_html_needs_no_external_tools() -> None:
    fmts = {f.key: f for f in export.available_formats()}
    assert fmts["html"].available is True
    assert fmts["html"].reason == ""


def test_available_formats_carry_no_reason_when_usable() -> None:
    for f in export.available_formats():
        if f.available:
            assert f.reason == ""


def test_missing_pandoc_disables_docx_with_an_actionable_reason() -> None:
    with patch.object(export, "pandoc_path", return_value=None):
        fmts = {f.key: f for f in export.available_formats()}
    assert fmts["docx"].available is False
    assert "pandoc" in fmts["docx"].reason
    assert fmts["html"].available is True  # HTML never depends on it


def test_missing_pdf_engine_is_named_separately() -> None:
    with patch.object(export, "pandoc_path", return_value="/usr/bin/pandoc"):
        with patch.object(export, "pdf_engine", return_value=None):
            fmts = {f.key: f for f in export.available_formats()}
    assert fmts["pdf"].available is False
    assert "engine" in fmts["pdf"].reason
    assert fmts["docx"].available is True  # DOCX doesn't need an engine


def test_html_renders_markdown_not_raw_markers(tmp_path: Path) -> None:
    out = tmp_path / "o.html"
    ok, _ = export.export(MD, out, "html", title="Chapter One")
    body = out.read_text(encoding="utf-8")
    assert ok
    assert "<h1>" in body and "<strong>" in body and "<em>" in body
    assert "**sleeps**" not in body           # markup was rendered, not printed
    assert "<title>Chapter One</title>" in body


def test_html_is_self_contained(tmp_path: Path) -> None:
    out = tmp_path / "o.html"
    export.export(MD, out, "html", title="t")
    body = out.read_text(encoding="utf-8")
    assert "<style>" in body                  # CSS inlined
    assert "http://" not in body and "https://" not in body


def test_html_escapes_the_title(tmp_path: Path) -> None:
    out = tmp_path / "o.html"
    export.export("x", out, "html", title="<script>bad</script>")
    assert "<title><script>" not in out.read_text(encoding="utf-8")


def test_pandoc_failure_returns_its_message(tmp_path: Path) -> None:
    with patch.object(export, "pandoc_path", return_value=None):
        ok, msg = export.export(MD, tmp_path / "o.docx", "docx")
    assert ok is False
    assert "pandoc" in msg


def test_unwritable_html_path_reports_rather_than_raises(tmp_path: Path) -> None:
    ok, msg = export.export(MD, tmp_path / "no-such-dir" / "o.html", "html")
    assert ok is False and msg

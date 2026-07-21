"""Turn a manuscript into something you can hand to someone else.

HTML is rendered in-process, so export always works. DOCX and PDF are handed to
pandoc when it is installed; when it isn't, the caller is told plainly rather
than shown a stack trace. Nothing here imports Textual.
"""

from __future__ import annotations

import html as _html
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Pandoc will happily accept a PDF target and then fail deep inside LaTeX if no
# engine is installed, so the engines are probed up front and named in order of
# preference.
_PDF_ENGINES = ("xelatex", "lualatex", "pdflatex", "tectonic", "typst", "wkhtmltopdf")

# Runaway conversions shouldn't hang the editor forever.
_PANDOC_TIMEOUT = 120


@dataclass(frozen=True)
class Format:
    key: str          # "html" | "docx" | "pdf" | "epub"
    label: str
    suffix: str
    available: bool
    reason: str = ""  # why it isn't available, shown to the user


def pandoc_path() -> str | None:
    return shutil.which("pandoc")


def pdf_engine() -> str | None:
    for engine in _PDF_ENGINES:
        if shutil.which(engine):
            return engine
    return None


def available_formats() -> list[Format]:
    """Every export target, each flagged with whether it can run right now."""
    pandoc = pandoc_path()
    no_pandoc = "needs pandoc — install it and reopen"
    engine = pdf_engine() if pandoc else None
    if not pandoc:
        pdf_reason = no_pandoc
    elif not engine:
        pdf_reason = "needs a PDF engine (e.g. xelatex or typst)"
    else:
        pdf_reason = ""
    def fmt(key: str, label: str, suffix: str, ok: bool, reason: str) -> Format:
        # A reason only makes sense when the format can't run — carrying one on
        # an available format would put "needs pandoc" next to a working row.
        return Format(key, label, suffix, ok, "" if ok else reason)

    return [
        fmt("html", "HTML — a self-contained web page", ".html", True, ""),
        fmt("docx", "DOCX — Word / Google Docs", ".docx", bool(pandoc), no_pandoc),
        fmt("pdf", "PDF — print-ready", ".pdf", bool(pandoc and engine), pdf_reason),
        fmt("epub", "EPUB — e-reader", ".epub", bool(pandoc), no_pandoc),
    ]


_CSS = """
:root { color-scheme: light dark; }
body {
  margin: 0 auto; padding: 4rem 1.5rem; max-width: 34rem;
  font: 1.05rem/1.7 Georgia, "Iowan Old Style", serif;
  color: #1a1a1a; background: #fdfdfb;
}
h1, h2, h3, h4 { font-family: system-ui, sans-serif; line-height: 1.25; margin: 2.4em 0 0.6em; }
h1 { font-size: 1.9rem; } h2 { font-size: 1.45rem; } h3 { font-size: 1.15rem; }
p { margin: 0 0 1.1em; }
blockquote { margin: 1.4em 0; padding-left: 1.1em; border-left: 3px solid #ccc; color: #444; }
code { font: 0.9em ui-monospace, monospace; background: #f0efe9; padding: 0.1em 0.3em; border-radius: 3px; }
pre { background: #f0efe9; padding: 1em; overflow-x: auto; border-radius: 4px; }
pre code { background: none; padding: 0; }
hr { border: none; border-top: 1px solid #ddd; margin: 2.5em 0; }
img { max-width: 100%; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 0.4em 0.6em; text-align: left; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e6e6; background: #16161a; }
  blockquote { border-left-color: #444; color: #b5b5b5; }
  code, pre { background: #22222a; }
  th, td { border-color: #333; }
  hr { border-top-color: #333; }
}
@media print { body { max-width: none; padding: 0; background: #fff; color: #000; } }
"""


def to_html(markdown_text: str, title: str) -> str:
    """Render Markdown to a standalone HTML page. Never needs external tools."""
    try:
        from markdown_it import MarkdownIt

        body = MarkdownIt("commonmark", {"typographer": True}).enable(
            ["table", "strikethrough"]
        ).render(markdown_text)
    except Exception:
        # Rendering should never be the reason an export fails outright; fall
        # back to preformatted text so the words still arrive.
        body = f"<pre>{_html.escape(markdown_text)}</pre>"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_html.escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def to_pandoc(
    markdown_text: str, out_path: Path, fmt: str, *, title: str = ""
) -> tuple[bool, str]:
    """Convert via pandoc. Returns (ok, message) — message is pandoc's own error."""
    pandoc = pandoc_path()
    if not pandoc:
        return False, "pandoc is not installed"
    cmd = [pandoc, "--from=commonmark_x", "--standalone", "--output", str(out_path)]
    if title:
        cmd += ["--metadata", f"title={title}"]
    if fmt == "pdf":
        engine = pdf_engine()
        if not engine:
            return False, "no PDF engine found (try installing xelatex or typst)"
        cmd += [f"--pdf-engine={engine}"]
    try:
        result = subprocess.run(
            cmd,
            input=markdown_text,
            capture_output=True,
            text=True,
            timeout=_PANDOC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"pandoc timed out after {_PANDOC_TIMEOUT}s"
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        return False, detail[-1] if detail else f"pandoc exited {result.returncode}"
    return True, str(out_path)


def export(
    markdown_text: str, out_path: Path, fmt: str, *, title: str = ""
) -> tuple[bool, str]:
    """Write ``markdown_text`` to ``out_path`` in ``fmt``. Returns (ok, message)."""
    if fmt == "html":
        try:
            out_path.write_text(to_html(markdown_text, title or out_path.stem), "utf-8")
        except OSError as exc:
            return False, str(exc)
        return True, str(out_path)
    return to_pandoc(markdown_text, out_path, fmt, title=title)

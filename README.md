# Prose

A terminal word processor for long-form Markdown.

**Status:** v0.1 in progress — **P0** shell + **P1** commands / menus / find.

## Docs

- [Prose v0.1 Design Specification](docs/PROSE_V0.1_DESIGN_SPEC.md)

## Quick start

```bash
cd Applications/prose
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
prose path/to/file.md    # or: python -m prose.app
pytest
```

### Keys (P0–P1)

| Key | Action |
|-----|--------|
| **F10** or **Ctrl+Shift+M** | Summon menus (←/→ switch menu, Enter run) |
| **Alt+F/E/V/…** | Jump to a menu *if* the terminal doesn’t steal Alt (see below) |
| Ctrl+S | Save |
| Ctrl+Z / Ctrl+Shift+Z | Undo / Redo |
| Ctrl+F / Ctrl+H | Find / Replace bar (Enter next, Shift+Enter prev, Esc close) |
| Ctrl+G | Go to line |
| Ctrl+A | Select all |
| Alt+Z | Toggle soft wrap |
| Ctrl+Q | Quit |

Open files from the CLI (`prose chapter.md`). Soft wrap on; status shows word count.

**Menus and the terminal:** many terminals (GNOME Terminal, etc.) keep **Alt** and sometimes **F10** for *their* menu bar, so those keys never reach Prose. Prefer **Ctrl+Shift+M**. To free Alt/F10, disable menu accelerators / F10 in the terminal’s preferences.

```bash
pytest   # 30 tests
```

## Stack

- Python 3.11+ / Textual
- CommonMark-native files on disk (hybrid MD rendering in later phases)
- Linux-first, Windows-compatible

## License

MIT — see [LICENSE](LICENSE).

## Feedback

daudzegir@gmail.com

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
| **F9** | Open the **menu ribbon** (File Edit View…); ←/→ switch, Enter run, Esc close |
| Ctrl+S | Save |
| Ctrl+Z / Ctrl+Shift+Z | Undo / Redo |
| Ctrl+F / Ctrl+H | Find / Replace bar (Enter next, Shift+Enter prev, Esc close) |
| Ctrl+G | Go to line |
| Ctrl+A | Select all |
| Alt+Z | Toggle soft wrap |
| Ctrl+Q | Quit |

Open files from the CLI (`prose chapter.md`). Soft wrap on; status shows word count.

**Menus:** Press **F9**.  
`Ctrl+Shift+P` is optional and often stolen by the host terminal/IDE before Prose receives it.  
Avoid Alt (terminals steal it) and Ctrl+M (same as Enter).

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

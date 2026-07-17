# Prose

A terminal word processor for long-form Markdown.

**Status:** v0.1 in progress — **P0** shell + document domain.

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

### P0 keys

| Key | Action |
|-----|--------|
| Ctrl+S | Save |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z | Redo |
| Ctrl+Q | Quit |

Open files from the CLI for now (`prose chapter.md`). Soft wrap is on; status line shows word count.

## Stack

- Python 3.11+ / Textual
- CommonMark-native files on disk (hybrid MD rendering in later phases)
- Linux-first, Windows-compatible

## License

MIT — see [LICENSE](LICENSE).

## Feedback

daudzegir@gmail.com

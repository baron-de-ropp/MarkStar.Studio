# MarkStar

**MarkStar** ([markstar.studio](https://markstar.studio)) — a Markdown-native terminal word processor. A modern homage to WordStar.

**Status:** v0.1 in progress — **P0–P2** (shell, menus/find, **multi-file tabs** + motion).

## Docs

- [Prose v0.1 Design Specification](docs/PROSE_V0.1_DESIGN_SPEC.md)

## Quick start

```bash
cd Applications/MarkStarStudio
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
markstar path/to/file.md    # or: python -m markstar.app
pytest
```

### Keys (P0–P1)

Every command is a single keystroke — no two-key chords, anywhere. Anything without a key lives in the menu (**F9** or **Esc**).

| Key | Action |
|-----|--------|
| **F9** / **Esc** | Open the **menu ribbon** (File Edit View Format Tools Project Help); ←/→ switch, Enter run, Esc close |
| **Ctrl+N** | New file |
| **Ctrl+O** | **Quick Open** — type a fragment to fuzzy-match recents + project files; `/` `~` `./` switches to a literal path with Tab-completion |
| **Ctrl+W** | Close tab — asks Save / Don't Save / Cancel if there are unsaved changes |
| **Ctrl+S** | Save (prompts for a path if the buffer is untitled) |
| **Ctrl+Q** | Quit — walks each unsaved buffer; `A` saves all, `Esc` cancels the quit |
| **Ctrl+Z** / **Ctrl+Y** | Undo / Redo |
| **Ctrl+F** / **Ctrl+R** | Find / Replace (Enter next or replace-one; ↑ prev; **Ctrl+L** replace all) |
| **Ctrl+A** | Select all |
| **Ctrl+B** / **Ctrl+E** | Bold / italic (`Ctrl+I` is Tab in a terminal, so italic is "E for emphasis") |
| **Ctrl+P** | Project panel — open+focus, focus, then close |
| **Ctrl+K** | StarBot AI panel |
| **Ctrl+G** / **F7** | Suggest spelling correction / toggle spellcheck |
| **Ctrl+←/→** | Word hop |
| **Ctrl+↑/↓** | Paragraph hop |
| **Ctrl+PageUp/PageDown** | Previous / next tab |

Menu-only (no key): Open Folder, Close Others, Close All, Save As, Save All, Compile, Duplicate Line, Move Line Up/Down, most Format commands, Soft Wrap, Zen Mode, Theme.

Launching with no file shows a task launcher: **Recent Files / Projects / New**, arrow through and press Enter. Open files from the CLI too (`markstar chapter.md`). Soft wrap on; status shows word count.  
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

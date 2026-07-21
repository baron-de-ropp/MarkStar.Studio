# MarkStar

**MarkStar** ([markstar.studio](https://markstar.studio)) — a Markdown-native terminal word processor. A modern homage to WordStar.

**Status:** v0.4 — file lifecycle, project search, outline, export, session restore.

## Docs

- [Keymap design](docs/MARKSTAR_KEYMAP.md) — what MarkStar binds, and why
- [Feature parity vs WordStar & MS Works](docs/research/FEATURE_PARITY.md)
- [Terminal key physics](docs/TERMINAL_KEY_PHYSICS.md) — what a TUI can and cannot bind
- [v0.1 design spec](docs/MARKSTAR_V0.1_DESIGN_SPEC.md) (historical)

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
| **F1** | Keyboard reference (every command, generated from the code) |
| **F3** | Find next — works from the text, no need to reopen the find bar |
| **F4** | Outline — jump to any Markdown heading |
| **F5** | Export to HTML / DOCX / PDF / EPUB (DOCX and PDF need pandoc) |
| **Ctrl+Home / Ctrl+End** | Start / end of the document |
| **Ctrl+←/→** | Word hop |
| **Ctrl+↑/↓** | Paragraph hop |
| **Ctrl+PageUp/PageDown** | Previous / next tab (see the note below) |

Inside the find bar: **Ctrl+T** toggles match-case, **Ctrl+L** replaces all, **Ctrl+R** expands to replace. With the project panel focused, **Ctrl+F** searches every file in the project.

Menu-only (no key): Open Folder, Close Others, Close All, Save As, Save All, Compile, Duplicate Line, Move Line Up/Down, most Format commands, Soft Wrap, Zen Mode, Theme.

Launching with no file shows a task launcher: **Recent Files / Projects / New**, arrow through and press Enter. If you had files open last time, the first row offers them all back, carets included. Open files from the CLI too (`markstar chapter.md`). Soft wrap on. The status strip counts *prose* — Markdown syntax, code blocks, link URLs and comments don't inflate the total — and shows the selection's count when you have one. Line numbers are an optional faint gutter (View → Line Numbers).  
Avoid Alt (terminals steal it) and Ctrl+M (same as Enter).

> **Tab switching in GNOME Terminal / other VTE terminals:** `Ctrl+PageUp` and
> `Ctrl+PageDown` are bound by the terminal itself to switch *its* tabs, so they
> never reach MarkStar. Either rebind them in the terminal's preferences, or use
> View → Next Tab / Previous Tab from the `F9` menu.

```bash
pytest
```

## Stack

- Python 3.11+ / Textual
- CommonMark-native files on disk (hybrid MD rendering in later phases)
- Linux-first, Windows-compatible

## License

MIT — see [LICENSE](LICENSE).

## Feedback

daudzegir@gmail.com

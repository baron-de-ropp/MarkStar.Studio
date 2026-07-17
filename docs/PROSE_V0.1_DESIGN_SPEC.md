# Prose v0.1 — Design Specification

**Status:** Frozen for implementation  
**Version:** 0.1.0  
**Date:** 2026-07-17  
**License:** MIT  
**Author / feedback:** daudzegir@gmail.com  

This document is the source of truth for building Prose v0.1. Changes that affect v0.1 behavior should update this spec. Ideas that do not block v0.1 go in [Later / roadmap](#12-later--roadmap).

---

## 1. Product identity

| Field | Value |
|--------|--------|
| **Name** | **Prose** |
| **CLI / binary** | `prose` |
| **Tagline (working)** | A terminal word processor for long-form Markdown |
| **AI agent (later)** | **ProseAI** (right panel; not shipped in v0.1) |
| **License** | MIT |
| **Repo** | User Gitea (potato); local workspace: `Documents/prose` |

### 1.1 What Prose is

- A **Linux-first**, Windows-compatible **terminal** application for writing **novels, essays, short stories**, and other long-form prose.
- **Native store = Markdown files on disk** (UTF-8). No proprietary document format.
- Feels like a light **~1998 word processor** (Works / Word–style menus and shortcuts), not Vim and not a full IDE.
- Keyboard-first; mouse optional (e.g. open links/images).

### 1.2 What Prose is not (v0.1)

- Not a WordStar keybinding clone (visual/cultural inspiration only where noted).
- Not Microsoft Word / layout DTP.
- Not Obsidian (no live embeds, no vault graph).
- Not a code editor (no multi-cursor, no camelCase subword, no column select in v0.1).
- Not cloud-native (normal folders; user syncs with external tools).

### 1.3 Name notes

- “Prose” is a common English word; fine for a personal/open-source TUI.
- **ProseMirror** is an unrelated web editor toolkit.
- **ProseAI** may be confused with legal “pro se” AI products; acceptable for now; rename later if needed.

---

## 2. Goals and non-goals

### 2.1 Goals (v0.1)

1. Open any Markdown file and write comfortably with soft wrap.
2. Hybrid Markdown display (styled off caret line; markers on focused line).
3. Classic WP menus (Alt) + predictable Ctrl bindings.
4. Multi-file tabs + optional project folder tree.
5. Safe autosave sidecars; full-session undo/redo.
6. Compile `![[include]]` into one Markdown file.
7. Spellcheck (English) with theme-colored underlines.
8. Find / replace; creature-comfort motion and selection.
9. Themable, airy TUI (OpenCode / Yazi / Grok-inspired hierarchy).

### 2.2 Non-goals (v0.1)

- GFM tables, task lists, footnotes as first-class hybrid UI.
- DOCX / ODT / PDF export (Pandoc later).
- ProseAI / LLM panel.
- Multi-cursor / select-all-occurrences.
- Grammar checking.
- AutoCorrect.
- Plugin system.
- VS Code theme file import (built-in themes only).
- Cloud sync, collaboration.

---

## 3. Document model and formats

### 3.1 Native format

- **Source of truth:** UTF-8 text files, typically `.md` / `.markdown`.
- **Dialect (v0.1):** [CommonMark](https://commonmark.org/) via a real parser library (do not hand-roll).
- **No internal binary/cache format** as the user-facing document.

### 3.2 Product extension: includes

| In editor | On compile |
|-----------|------------|
| `![[path-or-name]]` shown as a **token** (highlighted); **not** live-expanded | Resolve and stitch included file text into output |

- Not standard CommonMark; documented as a **Prose extension**.
- Resolve relative to the current file’s directory (and project root when a project is open).
- Handle missing files and include cycles with clear errors.

### 3.3 Emphasis rules

| Action | Behavior |
|--------|----------|
| **Ctrl+B / Ctrl+I insert** | Prefer **asterisks** (`**` / `*`) |
| **Render** | Both `*` and `_` emphasis forms display correctly |

### 3.4 Export (v0.1)

| Command | Behavior |
|---------|----------|
| **Save** | Write the active buffer to its path |
| **Compile Project…** | Flyout of targets; **only Markdown enabled** in v0.1: expand includes → one `.md` |

Later targets (same command): DOCX, ODT, PDF via Pandoc.

### 3.5 Images and links

- Syntax: `![alt](path)`, `[text](url)`.
- Hybrid display; optional badge when off-focus.
- **Open externally:** Ctrl+click and a menu command → OS default handler (`xdg-open` on Linux).
- No in-terminal image rendering (no sixel/kitty previews in v0.1).

---

## 4. Architecture

### 4.1 Stack

| Layer | Choice |
|-------|--------|
| Language | **Python 3** |
| TUI | **Textual** |
| Markdown | CommonMark-capable library + small include extension |
| Spellcheck | Hunspell or system dictionaries; **en_US** default |
| Packaging | Linux primary; Windows exe later (PyInstaller/Nuitka) |

### 4.2 Deep modules (seams)

```
UI (Textual shell)  →  CommandRegistry  →  Workspace / Document
                              ↓
                    services: fs, autosave, spellcheck, theme, compile
```

| Module | Responsibility |
|--------|----------------|
| **Document** | Buffer, selection, undo/redo ops, dirty flag, path |
| **Workspace** | Tabs, active doc, project root, open/close |
| **CommandRegistry** | id → handler, label, default key, menu path, enabled? |
| **MarkdownProfile** | Parse, hybrid highlight spans, include compile |
| **Filesystem port** | Read/write; test double for tests |
| **Spellcheck port** | Ranges of issues; suggestions |
| **Theme** | Semantic color roles → Textual CSS |

**Rule:** Widgets are thin. Menus, keys, and tests all invoke **commands**.

### 4.3 Patterns

- **Command pattern** for every menu item and keybinding.
- **Linear undo/redo:** undo stack + redo stack; new edit after undo clears redo; session-deep history (op-based, not full-file snapshots).
- **Debounced autosave** side effect on document change.
- **Projection:** screen = buffer + wrap + highlight layers + spell annotations.
- **Strategy (later):** Markdown dialect profiles (CommonMark → GFM → Obsidian-ish).

### 4.4 Suggested package layout

```text
prose/
  pyproject.toml / README.md / LICENSE
  docs/
    PROSE_V0.1_DESIGN_SPEC.md   ← this file
  src/prose/
    app.py
    commands/
    domain/          # document, workspace, edits
    markdown/        # profile, hybrid, compile_includes
    services/        # fs, autosave, spellcheck, open_external
    ui/              # editor, tabs, menu, project_panel, footer, dialogs
    config/          # defaults, load/save TOML, keybindings
  tests/
```

### 4.5 Large files

- Support documents **as large as RAM allows**.
- Prefer op-based undo; incremental wrap/highlight near edits; avoid full re-parse every keystroke on multi-MB files.
- Multi-file novels are the primary workflow; single huge files must still work.

---

## 5. User interface

### 5.1 Layout geography

```text
┌─ tabs (• dirty marker on tab) ─────────────────────────────┐
│  ┌ project ┐  ┌──── prose frame (vertical rules) ────┐ [ ] │
│  │  tree   │  │     ≤ zen_width cols, centered       │ AI  │
│  │  LEFT   │  │     scroll-past-end                  │RIGHT│
│  │ overlay │  │     faint scrollbar                  │later│
│  └─────────┘  └──────────────────────────────────────┘     │
├─ airy footer: spell · hints ···│··· words  L:C  dialect ──┤
└────────────────────────────────────────────────────────────┘
```

| Region | Role |
|--------|------|
| **Left** | Project tree (v0.1); **overlay** — does **not** shift prose |
| **Center** | Prose writing frame |
| **Right** | Reserved for **ProseAI** (later); overlay same rule |
| **Top** | Tabs; summonable menu bar |
| **Bottom** | Airy status footer |

### 5.2 Design language

| Inspiration | Apply to |
|-------------|----------|
| **OpenCode** | Welcome screen, modals, menu dropdowns: air, soft panels, one accent, dim tips |
| **Yazi** | Project tree: outline icons, comfy single-spaced density, quiet chrome |
| **Grok TUI** | Faint borders, footer spacing/pipes, breathing room |
| **MC dialogs** | Structure only (checkboxes, OK/Cancel) — **theme-native paint**, not DOS blue |

**Prose weight hierarchy:** editor text > filenames in tree > icons/carets (dimmest).

### 5.3 Prose frame

| Feature | Spec |
|---------|------|
| Soft wrap | **On by default**; toggleable |
| Zen / measure width | Configurable; **default 120 columns**; centered |
| Outer margin | Configurable; **default 5** when terminal width ≥ **90**, else **2**; never 0 |
| Vertical rules | Faint L/R rules framing the writing column |
| Scrollbar | Very faint |
| Scroll past end | Last line may sit at **top** of viewport with empty space below |
| Caret rescue | If user **types** while caret off-screen → scroll so caret is ~**top third** of prose viewport |
| Current line highlight | Toggle; when on, theme token background |
| Selection | Theme selection color |
| Bracket/markup match | Theme primary → secondary → tertiary cycle |
| Line number gutter | Toggle; default **off**; footer always has L:C |
| Hybrid Markdown | Default on: markers visible on **focused line**; styled off-focus |
| Show Markdown markers | Force source (always show `**` etc.) |
| Show typography marks | Tabs/trailing etc.; **no middle-dot on every space** |
| Caret | Beam/bar when terminal allows |

### 5.4 Tabs

- Multiple open files; active clearer, inactive dim.
- **Dirty:** `•` on the **tab** next to the name (not footer).
- Next/prev tab: Ctrl+Tab / Ctrl+Shift+Tab.

### 5.5 Project panel (left)

| Property | Spec |
|----------|------|
| Toggle | Ctrl+Shift+E (also View + Project menus) |
| Width | Configurable; **default 30 columns** |
| Layout effect | **Overlay** — prose does not shuffle L/R |
| Aesthetic | Yazi-like; **outline** mono icons; dimmer than prose |
| Icons | `tree.icons = outline \| off`; fallback ASCII `▸` `▾` `·`; **no emoji**; theme-tinted |
| Density | Single-spaced rows; dim chrome for “comfy,” not double-spacing |
| Header | Project root name |
| Active file | Highlighted |
| Open | Enter / activate opens in tab |
| File filter | See preferences: md emphasis / md only / all |

### 5.6 Find / Replace

- **Ctrl+F** / **Ctrl+H** → bar at **top of prose frame** (VS Code–like).
- **Enter** / **Shift+Enter** → next / previous (while find active).
- Esc dismisses.
- Footer does not morph into find.

### 5.7 Menus

- **Not always visible.** Summon: **Alt** or **Alt+letter** (e.g. Alt+F → File open).
- **Esc** dismisses / backs up.
- **F10** optional alias for menu bar.
- Thin top bar when summoned; **OpenCode-styled dropdowns** (soft panel, accent on row, dim shortcuts).
- Menu = catalog of **commands + keybindings**; arrow + Enter runs command; bindings always work without menu.

### 5.8 Modals / Preferences UI

- Centered soft panel, theme-native, OpenCode air.
- Checkboxes `[x]`/`[ ]`, fields, `[ OK ]` `[ Cancel ]`.
- Keys: arrows, Space toggle, Tab, Enter confirm, Esc cancel.
- Welcome / empty state: centered name, short actions, dim tips (OpenCode open-screen energy).

### 5.9 Footer

| Zone | Content |
|------|---------|
| Left | Spellcheck indicator |
| Center (dim) | Few classic hints (`^S save  ^B bold  ^F find  Alt menu`) |
| Right | **Word count** · **L:C** · **dialect** (e.g. CommonMark) |

### 5.10 Zen mode

- Full terminal focus; chrome minimized.
- Text measure still **≤ zen_width**, centered (no ultrawide wall of text).
- Project panel may still overlay.

---

## 6. Menus and commands

Top-level bar:

**File · Edit · View · Insert · Format · Tools · Project · Help**

### 6.1 File

| Command | Default key |
|---------|-------------|
| New File | Ctrl+N |
| New File in Project… | Ctrl+Shift+N |
| Open File… | Ctrl+O |
| Open Project Folder… | Ctrl+Shift+O |
| Close | Ctrl+W |
| Close All | Ctrl+Alt+W |
| Save | Ctrl+S |
| Save As… | Ctrl+Shift+S |
| Save All | Ctrl+Alt+S |
| Close Project Folder | (menu) |
| Recent files | submenu |
| Exit | Ctrl+Q |

### 6.2 Edit

| Command | Default key |
|---------|-------------|
| Undo | Ctrl+Z |
| Redo | Ctrl+Shift+Z |
| Cut / Copy / Paste | Ctrl+X / C / V |
| Select All | Ctrl+A |
| Find… | Ctrl+F |
| Find Next / Previous | Enter / Shift+Enter (in Find) |
| Replace… | Ctrl+H |
| Go To Line… | Ctrl+G |
| Expand / Shrink selection | Shift+Alt+→ / ← |
| Move line up / down | Alt+↑ / ↓ |
| Duplicate line | Ctrl+Shift+D |
| Delete word backward / forward | Ctrl+Backspace / Ctrl+Delete |

### 6.3 View

| Command | Default key |
|---------|-------------|
| Toggle Project Panel | Ctrl+Shift+E |
| Next / Previous Tab | Ctrl+Tab / Ctrl+Shift+Tab |
| Zen mode | F11 |
| Soft wrap | Alt+Z |
| Show Markdown markers | (menu / pref) |
| Show typography marks | (menu / pref) |
| Current line highlight | (menu / pref) |
| Line numbers | (menu / pref) |
| Theme… | (picker modal) |

### 6.4 Insert

Markdown writing aids (macros at cursor / around selection):

- Heading 1–4  
- Link…  
- Image…  
- Include file… → `![[…]]`  
- Horizontal rule  
- Bullet list / Numbered list  
- Block quote  
- Inline code / Code block  

### 6.5 Format

| Command | Default key |
|---------|-------------|
| Bold | Ctrl+B |
| Italic | Ctrl+I |
| Clear Formatting | Ctrl+\ |
| Paragraph style | Body, H1–H4, Quote, List (submenu) |

### 6.6 Tools

| Command | Default key |
|---------|-------------|
| Spelling… | (menu; user-bindable, e.g. F7) |
| Word Count… | (menu; live count also in footer) |
| Find in Project… | Ctrl+Shift+F |
| Preferences… | Ctrl+, |

No grammar, no AutoCorrect in v0.1.

### 6.7 Project

| Command | Default key |
|---------|-------------|
| Toggle Project Panel | Ctrl+Shift+E |
| Show Current File in Panel | (menu) |
| Find in Project… | Ctrl+Shift+F |
| Compile Project… | Ctrl+Shift+B |

Open/Close project folder live under **File** (hybrid IA).

### 6.8 Help

| Command | Notes |
|---------|--------|
| User Guide… | Bundled docs |
| Keyboard Shortcuts… | Full command list |
| Send Feedback… | mailto:daudzegir@gmail.com + joke that you likely won’t listen |
| About… | Name, version, MIT |

Later: Check for Updates; ProseAI.

---

## 7. Keybinding philosophy

| Modifier | Meaning |
|----------|---------|
| **Ctrl+Key** | Micro / this buffer |
| **Ctrl+Shift+Key** | Variant: other file, As…, broader scope |
| **Ctrl+Alt+Key** | All open tabs / session-wide (where appropriate) |
| **Forbidden** | Multi-step chords (no Ctrl+K then S) |

All bindings overridable in Preferences / config. Desktop may steal Ctrl+Alt combos — remap as needed.

### 7.1 Creature comfort motion

| Action | Keys |
|--------|------|
| Word left/right | Ctrl+← / → |
| Paragraph up/down | Ctrl+↑ / ↓ |
| Line start/end | Home / End |
| Doc start/end | Ctrl+Home / End |
| Page | PgUp / PgDn |
| Extend selection | Shift + any motion |

**Word boundary:** Word-like; `[A-Za-z0-9_’']+` with internal apostrophes; good enough for English prose.

**Expand selection ladder:** word → emphasis/code span → line → paragraph → document.

**Out of v0.1:** multi-cursor, select all occurrences, column select, camelCase subword.

---

## 8. Autosave and safety

| Event | Behavior |
|-------|----------|
| Edit (dirty) | Debounced write to sidecar (default **1500 ms**) |
| Sidecar path | Same directory: `.<filename>.autosave` (e.g. `.chapter-01.md.autosave`) |
| Explicit Save | Write real file; **delete sidecar** |
| Type again after save | New sidecar when dirty again |
| Open file | If sidecar newer than file → prompt Restore / Discard / Save As |

Original file is only replaced on explicit Save (or Save All), not on every keystroke.

---

## 9. Spellcheck

| Item | Spec |
|------|------|
| Language v0.1 | **English** (e.g. en_US) |
| Underlines | Theme token (not hard-coded red) |
| Grammar | **Out** of v0.1 |
| UI | Tools → Spelling… panel: suggestions, Ignore, Add, Change; advances through issues |
| Background | Underline unknown words when enabled |
| Performance | Prefer visible-region / debounced checks on large files |

Later: more languages; ProseAI for editorial passes (not green squiggles as Word grammar).

---

## 10. Configuration

### 10.1 Rule

**Any magic number, magic string, or toggle that operators might want → preference.**  
Keybindings are preferences too.

### 10.2 Location and format

| Platform | Path |
|----------|------|
| Linux | `~/.config/prose/config.toml` |
| Windows | `%APPDATA%\prose\config.toml` |

Format: **TOML**.

### 10.3 Seed schema (v0.1)

```toml
[editor]
zen_width = 120
outer_margin_wide = 5
outer_margin_narrow = 2
outer_margin_wide_min_cols = 90
soft_wrap = true
hybrid_markdown = true
show_markdown_markers = false
show_typography_marks = false
current_line_highlight = true
line_numbers = false
scroll_past_end = true
caret_rescue_ratio = 0.33

[project]
panel_width = 30
panel_open = false
tree_icons = "outline"       # outline | off
tree_show = "md_emphasis"    # md_emphasis | md_only | all

# md_emphasis: .md at normal tree dim; other files more dim
# md_only: hide non-markdown
# all: show everything; non-md still more dim than .md

[autosave]
enabled = true
debounce_ms = 1500
# sidecar: ".{name}.autosave" beside the file

[spellcheck]
enabled = true
language = "en_US"

[theme]
name = "darcula"             # built-ins: monokai, darcula, light, high_contrast, …

[files]
default_extension = "md"

[keybindings]
# overrides only, e.g.:
# save = "ctrl+s"
# toggle_project_panel = "ctrl+shift+e"
```

### 10.4 Themes (v0.1)

- Built-in palettes (Monokai, Darcula, light, high-contrast, etc.).
- Semantic roles: background, foreground, prose, selection, line_highlight, spell_error, tree_*, menu_*, accent, footer_dim, …
- **Later:** import VS Code theme JSON subset.

---

## 11. Implementation plan (build order)

Ship vertical slices; keep the app usable early.

| Phase | Deliverable |
|-------|-------------|
| **P0** | Document buffer, open/save, soft wrap, undo/redo, word count footer, basic Textual shell |
| **P1** | Command registry, keybindings, summonable menus, find/replace |
| **P2** | Tabs, workspace, creature-comfort motion/selection |
| **P3** | Hybrid CommonMark highlight; bold/italic commands |
| **P4** | Project panel overlay, tree, open folder |
| **P5** | Autosave sidecar + restore prompt |
| **P6** | Includes compile to Markdown |
| **P7** | Spellcheck underlines + spelling panel |
| **P8** | Themes, zen, margins, typography marks, preferences modal |
| **P9** | Polish: welcome, About, feedback mailto, Insert helpers, expand selection ladder |

---

## 12. Later / roadmap

Document only; not v0.1 scope.

| Area | Notes |
|------|--------|
| **ProseAI** | Right panel; API key; developmental / line / copy editing; toggle; **not** named Clippy |
| **GFM** | Tables (pretty off-edit, source on-edit), strikethrough, task lists, … |
| **Flavor profiles** | Obsidian-ish wikilinks, etc. |
| **Pandoc export** | DOCX, ODT, PDF from Compile Project… |
| **VS Code theme import** | After built-ins |
| **Grammar / multi-language spell** | |
| **Multi-cursor** | Explicitly hard in TUI; skip until proven |
| **Check for updates** | |
| **Plugins** | |
| **Split pane** | |
| **Project-local config** | `.prose/config.toml` |
| **macOS** as tier-1 | Not required for v0.1 |

---

## 13. Testing notes

- Prefer tests at **Document**, **CommandRegistry**, **compile_includes**, config load seams.
- Fake filesystem for autosave/sidecar tests.
- Snapshot or golden files for compile output.
- Manual TUI checklist for menus, zen, panel overlay stability.

---

## 14. Acceptance criteria (v0.1 “done”)

A user can:

1. Install/run `prose` on Linux.  
2. Open/create Markdown, type with soft wrap and hybrid bold/italic.  
3. Use Alt menus and Ctrl bindings without a mouse.  
4. Undo/redo deeply; Save clears autosave sidecar.  
5. Open a project folder, browse tree (md emphasized), multi-tab edit.  
6. Find/replace; word and paragraph hop; expand selection; move/duplicate line.  
7. Compile includes to a single Markdown file.  
8. See spell underlines and fix via Spelling panel.  
9. Switch built-in theme; adjust zen width and margins in Preferences.  
10. Send feedback via Help; see version in About.

---

## 15. Document history

| Date | Change |
|------|--------|
| 2026-07-17 | Initial freeze from design grilling session |

---

*End of Prose v0.1 Design Specification*

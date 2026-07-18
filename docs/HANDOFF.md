# Prose — session handoff

**Date:** 2026-07-18  
**Location:** `docs/HANDOFF.md` (in-repo; not `/tmp`)  
**Purpose of next session:** Resume v0.1 implementation after a break (continue from frozen design + committed UI/file/find work).  
**Repo:** `/home/daudzegir/Applications/prose`  
**Remote:** `https://source.ryanderopp.com/daudzegir/prose.git`  
**Stack:** Python 3.12, Textual 8.2.8, pytest; entry `prose` (MIT)

---

## How to resume (first 60 seconds)

```bash
cd /home/daudzegir/Applications/prose
.venv/bin/python -m pytest -q   # expect 49 passed as of this handoff
.venv/bin/prose                 # or: PYTHONPATH=src .venv/bin/python -m prose.app
```

**Authoritative product scope:** `docs/PROSE_V0.1_DESIGN_SPEC.md`  
**Scrollbar/margin geometry (already solved; don’t re-litigate):** `docs/SCROLLBAR_MARGIN_DIAG.md`  
**This handoff:** `docs/HANDOFF.md`

---

## Project status (honest)

- **~30–40% of v0.1** by design-spec phases / acceptance criteria.
- **Usable writer shell:** edit, tabs, save/open prompts, menus, find/replace, motion, layout polish.
- **Not started (major v0.1 remaining):** hybrid CommonMark, project panel, autosave sidecar, `![[include]]` compile, spellcheck, multi-theme/zen/preferences, expand-selection ladder, real file dialogs.

---

## What this session completed (committed with this handoff)

### UI: menus
- Replaced modal `MenuScreen` with in-layout **`MenuBar`** (`src/prose/ui/menu_bar.py`); deleted `menu_screen.py`.
- **Esc** summons/closes menu when idle; Esc dismisses find/modals first; **F9** still works.
- Footer hint: `Esc Menu`.

### Find / replace (worked hard with user on keys)
- Compact `FindBar` + soft multi-match highlights + bright selection for current hit.
- Match counter; seed from selection; live seek while typing.
- **Keys (user-chosen; do not invent new chords without asking):**

| Action | Key |
|--------|-----|
| Find | Ctrl+F |
| Replace bar | Ctrl+R |
| Next | Enter (find field) |
| Previous | Ctrl+Enter (confirmed working in user’s terminal) |
| Replace one | Enter (replace field) → replace then next |
| Replace all | Ctrl+Alt+R |
| Skip without replace | Focus find field (Ctrl+F / Tab) + Enter |
| Close bar | Esc |

- Domain: `step_find()` in `src/prose/domain/search.py`; tests in `tests/test_search.py`.
- Key normalization for capital letters: `src/prose/ui/keys.py`.
- **Ctrl+H** = Backspace in most terminals; do not map Backspace → replace. Ctrl+R is the real replace open key.

### File / workspace ops
- **Overwrite confirm** when Save/Save As targets an existing file that isn’t the buffer’s current path (`_ConfirmDialog`).
- **Save As** Ctrl+Shift+S hardened.
- **Save All** Ctrl+Alt+S: all *dirty* tabs; path-backed saved from `Document` (no TextArea round-trip race); untitled dirty get path prompts.
- **Open** Ctrl+O: path prompt (missing path → empty buffer on that path).
- **Close Others** (keep active): **menu only** — File → Close Others. Dirty confirm for *other* tabs.
- **Close All**: **menu only** — File → Close All.  
  **Do not rebind** Ctrl+Shift+W (closes whole terminal) or rely on Ctrl+Alt+W (often arrives as Ctrl+W).

### Layout (prior + still true)
- 5-col side margins; scrollbar flush right via left gutter + `ProseTextArea.wrap_width` (no right padding on TextArea).

---

## Known terminal binding landmines

| Chord | Reality |
|-------|---------|
| Ctrl+H | Often Backspace (ASCII 0x08) |
| Ctrl+Alt+* | Alt often stripped → falls through to Ctrl+* |
| Ctrl+Shift+W | Host closes terminal tab/window |
| Shift+Enter / Shift+F3 | Often not distinct |
| Ctrl+Enter | Works for this user (find prev) |

**Rule from user:** do **not** invent keybindings without asking; recommend options or ask.

---

## Architecture map (where code lives)

```
src/prose/
  app.py              # ProseApp shell, commands, modals, find wiring, ProseTextArea
  commands/registry.py
  domain/
    document.py       # undo/redo buffer, save/load
    workspace.py      # tabs; close_others / close_all / dirty_documents
    search.py         # find/replace pure helpers + step_find
    motion.py         # word/paragraph
  ui/
    menu_bar.py       # in-layout F9/Esc menu
    find_bar.py       # find/replace strip
    keys.py           # normalize_key, is_replace_all_key
    themes.py         # VSCODE_DARK
tests/                # 49 tests; domain-heavy
docs/
  PROSE_V0.1_DESIGN_SPEC.md
  SCROLLBAR_MARGIN_DIAG.md
```

---

## Suggested next work (when picking up)

Pick **one** vertical slice from the spec; good order after shell polish:

1. **P3** Hybrid CommonMark display + bold/italic commands (core product differentiator).
2. **P5** Autosave sidecar + restore (safety).
3. **P4** Project panel / open folder.
4. **P6** `![[include]]` compile.
5. **P7** Spellcheck.
6. **P8** Preferences / zen / multi-theme.

Avoid reopening scrollbar/margin geometry unless user reports a regression — see diagnostic doc.

---

## User preferences / process notes

- Linux-first TUI Markdown writer; Markdown on disk; no proprietary store.
- Keybinding philosophy (design): Ctrl = this buffer; **Ctrl+Shift** = across open tabs; **Ctrl+Alt** = bulk — but **terminals break Alt/Ctrl+Shift often**; prefer proven chords or menu-only.
- Esc menus (not Alt — terminals steal Alt).
- Grill/ask rather than thrashing keys.
- No multi-step key chords if avoidable.
- ~35% of v0.1; user closing project to resume later.

---

## Suggested skills for the next agent

| Skill | Why |
|-------|-----|
| **codebase-design** | New modules (markdown profile, project panel, autosave) — keep deep modules / clean seams. |
| **tdd** | Domain logic (includes, autosave, spell) should stay pure + tested like `search`/`document`. |
| **diagnosing-bugs** | Terminal key-delivery issues; Textual focus/binding priority traps. |
| **handoff** | When pausing again, regenerate an updated handoff. |
| **grilling** | Before large P3–P7 scope, pressure-test approach with the user. |

Do **not** invent keybindings without asking the user.

---

## Quick manual smoke (optional after pull)

1. Esc → menu → File/Edit/View/Help  
2. Ctrl+F / Enter / Ctrl+Enter / Ctrl+R / Enter in replace / Ctrl+Alt+R  
3. Ctrl+N → Ctrl+S → overwrite confirm on existing path  
4. Two dirty path tabs → Ctrl+Alt+S  
5. Multi-tab → Esc → File → Close Others  
6. Soft wrap Alt+Z; word hop Ctrl+Left/Right  

---

## Out of scope for v0.1 (don’t start unless asked)

ProseAI, full GFM, Pandoc export, plugins, multi-cursor, VS Code theme import — see design spec §12.

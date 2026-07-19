# Prose — session handoff

**Date:** 2026-07-18  
**Location:** `docs/HANDOFF.md` (in-repo; not `/tmp`)  
**Purpose of next session:** **Fix Replace All key delivery** (blocking UX). Domain `replace_all()` works; real terminal does not fire the chord. Do not invent new chords without asking the user.  
**Repo:** `/home/daudzegir/Applications/prose`  
**Remote:** `https://source.ryanderopp.com/daudzegir/prose.git`  
**Stack:** Python 3.12, Textual 8.2.8, pytest; entry `prose` (MIT)  
**Branch:** `main` (local mods uncommitted — see [Working tree](#working-tree-as-of-handoff))

---

## How to resume (first 60 seconds)

```bash
cd /home/daudzegir/Applications/prose
.venv/bin/python -m pytest -q   # expect 52 passed as of this handoff
.venv/bin/prose                 # or: PYTHONPATH=src .venv/bin/python -m prose.app
```

**Authoritative product scope:** `docs/PROSE_V0.1_DESIGN_SPEC.md`  
**Scrollbar/margin geometry (already solved; don’t re-litigate):** `docs/SCROLLBAR_MARGIN_DIAG.md`  
**This handoff:** `docs/HANDOFF.md`

---

## BLOCKER for next agent: Replace All never fires in user’s terminal

### Symptom (user-confirmed)

| Chord tried | User result |
|-------------|-------------|
| **Ctrl+Alt+R** (old) | Did not replace all |
| **Ctrl+Shift+R** (after Alt removal) | Did not replace all / no “Replaced N occurrence(s)” |
| **Ctrl+Shift+Enter** (current primary) | Still not replace all |

**User-confirmed working (same session / prior):**

| Chord | Works? |
|-------|--------|
| Esc / F9 menu open, ←/→ across menus | Yes |
| Find / replace bar generally | Yes |
| Ctrl+Enter = find previous | Yes |
| Ctrl+R = open/expand replace | Yes (and was the fall-through when Alt was stripped) |
| Scrollbar flush + 5-col margin | Yes (user: “scrollbar seems to be working”) |
| Terminal landmines around Alt menus | Considered resolved by dropping Alt |

### What is *not* broken

- **Domain logic:** `prose.domain.search.replace_all()` is correct and unit-tested (`tests/test_search.py`).
- **App command:** `ProseApp.cmd_replace_all()` works when invoked:
  - Syncs editor → document, reads find/replace fields, calls `replace_all`, pushes text back, notifies `Replaced N occurrence(s)`.
- **Headless pilot proof** (agent ran; code path OK when Textual *receives* the key name):

```text
pilot.press("ctrl+shift+r")     → OK  "foo bar foo baz foo" => "X bar X baz X"
pilot.press("ctrl+shift+enter") → OK  same
pilot.press("shift+ctrl+r")     → OK  after modifier-order normalize
pilot.press("ctrl+r")           → does NOT replace all (by design: open/expand replace)
```

So this is almost certainly a **key delivery / binding precedence / focus** problem in the *real* terminal, not a search bug.

### Strongest working theory

**Stacked modifiers (Alt, and often Shift on top of Ctrl) are stripped or remapped by the host before Prose sees them.**

Classic degradation pattern already proven for this app:

| User presses | Terminal may deliver | What Prose does today |
|--------------|----------------------|------------------------|
| Ctrl+Alt+R | `ctrl+r` | Open/expand replace (not all) |
| Ctrl+Shift+R | `ctrl+r` (Shift lost) **or nothing** (host steals) | Open/expand replace or no-op |
| Ctrl+Shift+Enter | `ctrl+enter` (Shift lost) | **Find previous** — looks like “nothing useful for replace all” |

That last row is why **Ctrl+Shift+Enter is a bad primary** on this user’s machine if Shift is stripped: it silently becomes the *working* find-prev chord.

**Ctrl+Enter works** as find prev → Ctrl *alone* with Enter is delivered. Adding Shift on top may not survive.

Hosts that often steal **Ctrl+Shift+R:** browsers (hard reload), IDEs, some terminal profiles. User environment is Linux TUI; may be a full terminal emulator or an IDE integrated terminal — **not confirmed which**.

### What was already changed (uncommitted local work)

1. **Policy: no Alt** for product chords. Ctrl+Alt bulk ops re-chorded to Ctrl+Shift.
2. **Remap table applied in code/docs:**

| Action | Old | Current (intended) |
|--------|-----|---------------------|
| Replace All | Ctrl+Alt+R | **Ctrl+Shift+Enter** primary; Ctrl+Shift+R secondary |
| Save All | Ctrl+Alt+S | Ctrl+Shift+A |
| Move line | Alt+↑/↓ | Ctrl+Shift+↑/↓ |
| Soft wrap | Alt+Z | Ctrl+Shift+L |

3. **`src/prose/ui/keys.py`:** `normalize_key()` lowercases letter segments + canonicalizes modifier order (`shift+ctrl+r` → `ctrl+shift+r`). `is_replace_all_key()`, `is_save_all_key()`.
4. **Handlers check replace-all before bare `ctrl+r`** in `FindInput` and `ProseApp.on_key`.
5. **FindInput** intercepts bulk keys before Textual `Input` defaults (notably Input binds `ctrl+shift+a` → select all, which would eat Save All).
6. **Docs** (README, design spec key tables, this handoff) updated for no-Alt policy.
7. **Tests:** 52 passing; `tests/test_keys.py` covers normalize + replace-all/save-all helpers.

### Code map (read these first)

| File | Role |
|------|------|
| `src/prose/ui/keys.py` | `_REPLACE_ALL_KEYS`, `normalize_key`, `is_replace_all_key` |
| `src/prose/ui/find_bar.py` | `FindInput._on_key`, `FindBar.BINDINGS`, hints UI, `action_replace_all` → `ReplaceRequested("all")` |
| `src/prose/app.py` | `BINDINGS` for replace all / find prev; `on_key` fallback; `cmd_replace_all`; `action_replace_all_key`; registry id `replace_all` |
| `src/prose/domain/search.py` | `replace_all(document, query, replacement) -> int` (pure; tested) |
| `tests/test_keys.py` | Chord helper unit tests |
| `tests/test_search.py` | Domain replace-all |

**Message path when key is recognized:**

```text
FindInput._on_key / FindBar binding / App binding / App.on_key
  → ReplaceRequested("all") or action_replace_all / action_replace_all_key
  → ProseApp.cmd_replace_all()
  → domain.replace_all(...)
  → notify "Replaced N occurrence(s)"
```

**Dangerous fallback order in `FindInput` (current):** after replace-all check, `ctrl+enter` always posts find **prev**. If Shift is stripped from Ctrl+Shift+Enter, user gets prev, not all.

**Dangerous fallback in `App.on_key`:** same — `ctrl+enter` → `cmd_find_prev`.

### Suggested diagnostic (do this before inventing another chord)

1. **Prove the command without any chord:** with find bar open, find string set, replace string set → **Esc → Edit → Replace All** (menu). If that shows `Replaced N…`, command is fine (expected).
2. **Key logger (temporary):** while find bar is open, on every `events.Key` with modifiers, `notify(f"key={event.key!r}")` once (or write to a debug file). Ask user to press Ctrl+Shift+Enter and Ctrl+Shift+R and report the string. That ends the guesswork.
3. **Pilot already proves** the happy path; don’t re-prove domain unless logger shows the right key *and* replace still fails.

### Suggested fix directions (pick with user — do not invent alone)

Rule from user: **do not invent keybindings without asking; recommend options or ask.**

Promising directions given **Ctrl+Enter is proven**:

| Option | Idea | Pros | Cons |
|--------|------|------|------|
| **A. Context-sensitive Ctrl+Enter** | Find field focused → prev; **replace field focused → replace all** | Uses only a known-good chord | Changes meaning of Ctrl+Enter by focus; must document in bar hints |
| **B. Function key** | e.g. **F4** = replace all when find open | Single key, hard to strip | Need user OK; some hosts bind F-keys |
| **C. Menu only** | Edit → Replace All; no chord | Always works | Worse power-user UX |
| **D. In-bar control** | Focusable “All” affordance / button in find strip | No modifier stack | More UI work |
| **E. Keep trying Ctrl+Shift+*** | Only if logger shows Shift *is* delivered | Matches policy | Already failed twice for this user |

**Recommendation to next agent:** run the key logger with the user first; then implement **A and/or B** with explicit user sign-off. Stop cycling Ctrl+Shift letter/enter variants without evidence.

Also verify **Save All (Ctrl+Shift+A)** and **soft wrap (Ctrl+Shift+L)** / **move line (Ctrl+Shift+↑↓)** in the same session — same family of risk; user has not confirmed those yet.

---

## Working tree as of handoff

Uncommitted relative to `origin/main`:

```text
 M README.md
 M docs/HANDOFF.md
 M docs/PROSE_V0.1_DESIGN_SPEC.md
 M src/prose/app.py
 M src/prose/ui/find_bar.py
 M src/prose/ui/keys.py
 M tests/test_keys.py
?? untitled.md untitled2.md   # user scratch; ignore
```

**52 tests pass.** Do not discard this work — it contains the no-Alt policy and chord remaps even though Replace All still fails in the live terminal.

---

## Project status (broader)

- **~30–40% of v0.1** by design-spec phases.
- **Usable shell:** edit, tabs, menus, find/replace (except replace-all chord), motion, layout, scrollbar fix.
- **Not started (major):** P3 hybrid CommonMark, P4 project panel, P5 autosave, P6 `![[include]]` compile, P7 spellcheck, P8 themes/zen/prefs, P9 polish.

**After replace-all is fixed**, suggested product order remains: P3 → P5 → P4 → P6 → …

---

## Find / replace keys (intended — live terminal not fully verified)

| Action | Key | User verified? |
|--------|-----|----------------|
| Find | Ctrl+F | Informal / yes |
| Replace bar | Ctrl+R | Yes |
| Next | Enter (find field) | Yes |
| Previous | Ctrl+Enter | **Yes** |
| Replace one | Enter (replace field) → replace then next | Believed yes |
| Replace all | Ctrl+Shift+Enter (primary), Ctrl+Shift+R (secondary), Edit menu | **No — broken in live terminal** |
| Close bar | Esc | Yes |

- Domain: `src/prose/domain/search.py`; tests `tests/test_search.py`.
- **Ctrl+H** = Backspace in most terminals; never map Backspace → replace.

---

## Keybinding policy (current product rule)

| Tier | Use |
|------|-----|
| **Ctrl** | This buffer |
| **Ctrl+Shift** | Stronger / multi-tab / bulk (*when host delivers Shift*) |
| **Menu only** | Close Others, Close All; fallback for anything host steals |
| **Esc / F9** | Menus (**never Alt**) |
| **No Alt / Ctrl+Alt** | Terminals strip Meta |

### Landmines

| Chord | Reality |
|-------|---------|
| Ctrl+H | Often Backspace |
| Alt / Ctrl+Alt+* | Stripped or stolen — do not use |
| Ctrl+Shift+W | Host closes terminal |
| Ctrl+Shift+R | Often stolen (reload/IDE) **or** Shift stripped → ctrl+r |
| Ctrl+Shift+Enter | Suspected Shift stripped → ctrl+enter → find prev |
| Ctrl+Enter | **Works for this user** (find prev) |

---

## Architecture map

```
src/prose/
  app.py              # ProseApp shell, commands, modals, find wiring, ProseTextArea
  commands/registry.py
  domain/
    document.py       # undo/redo buffer, save/load
    workspace.py      # tabs
    search.py         # find/replace pure helpers
    motion.py
  ui/
    menu_bar.py
    find_bar.py       # find/replace strip + key intercept
    keys.py           # normalize_key, is_replace_all_key, is_save_all_key
    themes.py
tests/                # 52 tests; domain-heavy; almost no pilot/UI tests
docs/
  PROSE_V0.1_DESIGN_SPEC.md
  SCROLLBAR_MARGIN_DIAG.md
  HANDOFF.md          # this file
```

---

## User preferences / process

- Linux-first TUI Markdown writer; Markdown on disk.
- **Do not invent keybindings without asking**; recommend options or ask.
- Grill rather than thrash keys.
- No multi-step chords if avoidable.
- Prefer proven chords or menu-only over “should work” modifier stacks.

---

## Suggested skills for the next agent

| Skill | Why |
|-------|-----|
| **diagnosing-bugs** | Terminal key delivery; Textual focus/binding priority |
| **tdd** | Any pure key-normalize or context-sensitive routing |
| **grilling** | Before committing a new replace-all chord with the user |

Do **not** invent keybindings without asking the user.

---

## Out of scope for v0.1 (don’t start unless asked)

ProseAI, full GFM, Pandoc export, plugins, multi-cursor, VS Code theme import — see design spec §12.

---

## One-paragraph brief for the next model

Prose is a Textual Markdown writer at `~/Applications/prose`. Replace All’s **domain and `cmd_replace_all` work**; headless `pilot.press("ctrl+shift+enter")` and `ctrl+shift+r` succeed. The **user’s live terminal does not** — Ctrl+Alt+R, Ctrl+Shift+R, and Ctrl+Shift+Enter all failed to replace all. Ctrl+Enter (find prev) and Ctrl+R (open replace) work. Likely cause: host strips Shift/Alt so stacked chords degrade into existing Ctrl-only bindings (`ctrl+r` / `ctrl+enter`). Next step: temporary key logger to print `event.key`, confirm delivery, then with user approval implement a **non-stacked** replace-all trigger (best candidates: Ctrl+Enter when replace field focused, and/or F4, and/or menu-only). Uncommitted no-Alt rebind work is on disk; 52 tests pass; do not reopen scrollbar geometry.

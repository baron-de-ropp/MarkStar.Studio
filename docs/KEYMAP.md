# Prose — portable keymap (proposal for sign-off)

**Status:** DRAFT — awaiting user approval. No bindings changed yet.
**Date:** 2026-07-18
**Supersedes:** the "no-Alt / Ctrl+Shift tier" policy in `HANDOFF.md` and the key tables in `PROSE_V0.1_DESIGN_SPEC.md`.
**Goal:** one keymap that behaves the same in every terminal on Linux, macOS, and Windows — "Microsoft Works 1995, in the terminal."

---

## 1. The one idea everything follows from

**Your app does not talk to the operating system. It talks to a terminal emulator, and the emulator decides which key events you receive.** The same binary in `kitty` vs `Terminal.app` on the *same Mac* gets different keys. tmux and SSH each add another remapping layer on top.

So "cross-OS" is the wrong axis. The axis is **cross-terminal-emulator**, and the dividing line is one feature:

- **Legacy terminals** (xterm, gnome-terminal, macOS Terminal.app, older Windows conhost, most tmux/SSH sessions) encode `Ctrl`+letter as a **single control byte**. `Ctrl+R` and `Ctrl+Shift+R` are **the same byte** (`0x12`). Shift is not representable. `Ctrl+Enter` == `Enter`. This is why three sessions of rebinding Replace All onto `Ctrl+Shift+*` failed — the information never arrived.
- **Kitty-protocol terminals** (kitty, Ghostty, foot, WezTerm, recent Konsole, alacritty w/ config) report modifiers as explicit bitflags, so `Ctrl+Shift+Enter` is a genuinely distinct event. Textual enables this automatically **when the terminal supports it.**

We cannot require the second group. So we design for the first and *enhance* for the second.

### macOS correction (important)

**`Cmd` is owned by the terminal emulator, not by us.** `Cmd+C`, `Cmd+T`, `Cmd+W`, `Cmd+Q` are Terminal.app / iTerm2 shortcuts; by default `Cmd`-combos are **never delivered to the TUI app at all.** So we do **not** build a Mac-specific `Cmd`+key map — it wouldn't work. On Mac terminals, `Ctrl` behaves exactly as it does on Linux/Windows, and that's what every Mac terminal user already expects (vim, tmux, emacs, htop all use `Ctrl`). **One keymap, all platforms.**

---

## 2. Three-tier delivery model

Every command is assigned a tier for *how it is reached*:

| Tier | What | Reaches | Rule |
|------|------|---------|------|
| **0 — Guaranteed** | The menu (Esc / F9 → File/Edit/View/Help) and the command reachable inside it | **Every** terminal, every OS, through tmux/SSH | **Every command MUST have a Tier-0 path.** This is the safety net. |
| **1 — Portable keys** | Single printable char, single `Ctrl`+letter (non-reserved), bare `F`-keys (non-stolen), `Enter`, `Tab`, `Esc`, arrows, `Ctrl`+arrows, `Ctrl`+PageUp/Down | Virtually all terminals | Primary shortcuts live here. |
| **2 — Enhanced keys** | `Ctrl+Shift+*`, `Ctrl+Enter`, `Shift+Enter`, `Ctrl+Alt+*`, `Shift+F`-keys | Only Kitty-protocol terminals (and this user's, which delivers `Ctrl+Enter`) | Offered as **bonus aliases only**, never the sole path. |

The bug in the current design: bulk commands (Replace All, Save All, move-line, tab-switch) are **Tier-2-only**. On a legacy terminal they have no reachable key. The fix is to give each a Tier-1 key and/or lean on its Tier-0 menu entry, and demote the `Ctrl+Shift` chords to Tier-2 aliases.

---

## 3. Reliability reference (what encodes how)

**Rock-solid everywhere (Tier 1):**
- Printable characters
- `F1`–`F12` *(escape sequences, not modifier stacks)* — but see "stolen F-keys" below
- Arrows, `Home`/`End`, `PageUp`/`PageDown`, `Tab`, `Enter`, `Backspace`, `Esc`
- Single `Ctrl`+letter **except the reserved set**
- `Ctrl`+arrows, `Ctrl`+`PageUp`/`PageDown` *(distinct sequences in almost all terminals; verify via keyprobe)*

**Reserved / dangerous `Ctrl`+letter — do not bind to these:**
| Key | Why |
|-----|-----|
| `Ctrl+I` | == Tab |
| `Ctrl+M` | == Enter |
| `Ctrl+J` | == Line feed |
| `Ctrl+H` | == Backspace on most terminals |
| `Ctrl+[` | == Esc |
| `Ctrl+C` | SIGINT |
| `Ctrl+Z` | Suspend (usable *because* Textual takes raw mode — we use it for Undo) |
| `Ctrl+S` / `Ctrl+Q` | XON/XOFF flow control — will **freeze the terminal** unless raw mode disables it (Textual does; keep verifying) |
| `Ctrl+D` | EOF |
| `Ctrl+\` | SIGQUIT |

**Stolen F-keys (avoid or make optional):** `F1` (help in some emulators), `F10` (menu in gnome-terminal), `F11` (fullscreen in many). We already use **F9** for menu specifically to dodge F10. Avoid F10/F11 for commands.

**Not reliable without Kitty protocol (Tier 2 only):** `Ctrl+Shift+anything`, `Ctrl+Enter`, `Shift+Enter`, `Ctrl+Alt+anything`. `Alt`+letter is semi-portable but collides with Esc-timing and is hijacked on macOS (Option → accented chars) — **we avoid Alt entirely.**

---

## 4. Proposed Prose keymap

Legend: **Menu** = Tier-0 guaranteed path · **Key** = Tier-1 portable shortcut · **Enhanced** = Tier-2 alias (kept for capable terminals, never required).

### File
| Command | Menu | Key (Tier 1) | Enhanced (Tier 2) | Change? |
|---------|------|--------------|-------------------|---------|
| New File | File | `Ctrl+N` | — | keep |
| Open File… | File | `Ctrl+O` | — | keep |
| Close | File | `Ctrl+W` | — | keep |
| Close Others | File | *(menu only)* | — | keep |
| Close All | File | *(menu only)* | — | keep |
| Save | File | `Ctrl+S` | — | keep |
| Save As… | File | *(menu only)* | `Ctrl+Shift+S` | **was Ctrl+Shift+S primary** |
| Save All | File | *(menu only)* | — | **was Ctrl+Shift+A primary** |
| Exit | File | `Ctrl+Q` | — | keep |

### Edit
| Command | Menu | Key (Tier 1) | Enhanced (Tier 2) | Change? |
|---------|------|--------------|-------------------|---------|
| Undo | Edit | `Ctrl+Z` | — | keep |
| Redo | Edit | **`Ctrl+Y`** | `Ctrl+Shift+Z` | **was Ctrl+Shift+Z only** |
| Find… | Edit | `Ctrl+F` | — | keep |
| Replace… | Edit | `Ctrl+R` | — | keep |
| Find Next | Edit | `Enter` (in find field) · **`F3`** | — | **add F3** |
| Find Previous | Edit | **`Shift+F3`** | `Ctrl+Enter` | **was Ctrl+Enter only** |
| Replace | Edit | `Enter` (in replace field) | — | keep |
| **Replace All** | **Edit** | **`F4`** (find bar open) | `Ctrl+Shift+Enter`, `Ctrl+Shift+R` | **was Ctrl+Shift+Enter only — the whole reason for this doc** |
| Select All | Edit | `Ctrl+A` | — | keep |
| Duplicate Line | Edit | *(menu only)* | `Ctrl+Shift+D` | **was Ctrl+Shift+D only** |
| Move Line Up | Edit | *(menu only)* | `Ctrl+Shift+Up` | **was Ctrl+Shift+Up only** |
| Move Line Down | Edit | *(menu only)* | `Ctrl+Shift+Down` | **was Ctrl+Shift+Down only** |

### View
| Command | Menu | Key (Tier 1) | Enhanced (Tier 2) | Change? |
|---------|------|--------------|-------------------|---------|
| Next Tab | View | **`Ctrl+PageDown`** | `Ctrl+Shift+.` | **was Ctrl+Shift+. only (6 spellings)** |
| Previous Tab | View | **`Ctrl+PageUp`** | `Ctrl+Shift+,` | **was Ctrl+Shift+, only (6 spellings)** |
| Soft Wrap | View | *(menu only)* | `Ctrl+Shift+L` | **was Ctrl+Shift+L only** |

### Global / menu
| Command | Key |
|---------|-----|
| Open Menu | `Esc` (primary) · `F9` (alt) · `Ctrl+Shift+P` (Tier-2 alias) |
| Menu navigation | `←`/`→` across menus · `↑`/`↓` in dropdown · `Enter` select · first-letter mnemonic (`F`/`E`/`V`/`H`) |
| Help | *(menu: Help)* · **`F1`** if not stolen |

### Motion (already portable — no change)
`Ctrl+←`/`Ctrl+→` word · `Ctrl+↑`/`Ctrl+↓` paragraph. All Tier 1.

---

## 5. Why these specific picks

- **`Ctrl+Y` for Redo** — the Windows/classic-editor convention, a clean single `Ctrl`+letter. `Ctrl+Shift+Z` stays as a Mac-muscle-memory alias for capable terminals.
- **`F4` for Replace All** — a bare F-key is a single unambiguous sequence, unstealable by legacy encoding. F4 avoids the stolen F1/F10/F11. It only needs to fire when the find bar is open, so it can't collide with anything. (Note: `Alt+F4` closes windows on Windows — but *bare* F4 is free.)
- **`F3` / `Shift+F3` for Find Next/Prev** — the near-universal editor convention. Bare F3 is Tier 1. `Shift+F3` gets its own escape sequence on most terminals (unlike `Ctrl+Shift+letter`), so it's *mostly* portable; the menu and plain `Enter` guarantee coverage where it isn't.
- **`Ctrl+PageDown`/`Ctrl+PageUp` for tabs** — what browsers and editors use; encodes reliably far more often than `Ctrl+Shift+punctuation`. **Bonus:** this lets us delete the `ProseTextArea` angle-bracket interception hack and the six-spelling `_NEXT_TAB_KEYS`/`_PREV_TAB_KEYS` frozensets — a real simplification.
- **Move-line / Duplicate / Soft-wrap → menu-primary** — low-frequency power ops. Menu is guaranteed; the `Ctrl+Shift` chord stays as a Tier-2 nicety. (If you want a Tier-1 key for move-line, the only clean single-key options are F-keys — flagged as an open decision below.)

---

## 6. Progressive enhancement (the *right* use of Ctrl+Shift)

At startup, detect whether the terminal negotiated the Kitty protocol. **If yes,** the Tier-2 aliases (`Ctrl+Shift+Enter`, `Ctrl+Enter`, `Ctrl+Shift+arrows`, …) all work as bonus shortcuts. **If no,** they silently do nothing and the user relies on Tier-1 keys + menu. Either way nothing *breaks*. This is the only correct role for stacked modifiers: an enhancement, never a dependency.

The footer hint strip and menu shortcut column should show **Tier-1 keys** (the ones that always work), not the Tier-2 chords — so we never advertise a key that a given terminal can't deliver.

---

## 7. How we verify (not with pilot.press)

Portability **cannot** be unit-tested: `pilot.press("ctrl+shift+enter")` injects the decoded key *name* and bypasses the terminal decoder — the exact layer that fails. It can only ever pass. Real verification is `tools/keyprobe.py` run in real emulators:

| Platform | Terminals to probe |
|----------|--------------------|
| Linux | gnome-terminal, xterm, kitty, alacritty, konsole |
| macOS | Terminal.app, iTerm2, kitty/Ghostty |
| Windows | Windows Terminal, conhost |
| Layered | any of the above **through tmux** and **through SSH** |

For each, press `F3`, `F4`, `Shift+F3`, `Ctrl+PageUp/Down`, `Ctrl+Y`, and confirm they arrive as themselves. The probe's banner reports whether the Kitty protocol is active (i.e. whether the Tier-2 aliases will also work there). Record results in a matrix appended to this doc.

`pilot.press` *is* fine for testing **command wiring** (menu → registry → handler), because menu nav uses only reliable keys. That's how we already proved `Edit → Replace All` works end to end.

---

## 8. Open decisions for sign-off

1. **Replace All key = `F4`?** Or a different free F-key (`F5`–`F8`), or menu-only + an in-bar `[All]` button?
2. **Redo = `Ctrl+Y`?** (Recommended.) Keep `Ctrl+Shift+Z` as alias — yes/no?
3. **Tabs = `Ctrl+PageUp/PageDown`?** (Recommended; also deletes the angle-bracket hack.)
4. **Move-line / Duplicate-line:** menu-only, or spend an F-key on them?
5. **Soft-wrap:** menu-only (View), or give it a Tier-1 `Ctrl+L`?
6. **Show F1 = Help**, or leave Help menu-only (F1 is stolen by some emulators)?

Once you sign off on 1–6, the code changes are mechanical: rewrite the `BINDINGS` lists and the `add(...)` binding strings in `app.py`, update the `keys.py` helper sets, drop the tab-key hacks, point the footer/menu hints at Tier-1 keys, and refresh the docs. Tests stay green (they exercise the command/domain layer, not key delivery).

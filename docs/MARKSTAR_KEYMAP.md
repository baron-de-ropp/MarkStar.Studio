# MarkStar Studio — keymap design (single-stroke + menu)

**Status:** Piece #1 (keymap cleanup + Format menu + Replace All wiring) **DONE**. Piece #2 (inline formatting display, §5b) **DONE** + theme token system with two themes (`vscode-dark`, `markstar-light`) and View → Switch Theme / Formatting Preview. 64 tests pass.
**Date:** 2026-07-18
**Builds on:** `KEYMAP.md` (terminal-portability physics — still valid).
**Positioning:** A Markdown-native reimagining of WordStar — modern, approachable, menu-driven like Microsoft Works. **No memorized two-stroke chords, anywhere.**

---

## 1. Design principles

1. **Every shortcut is a single keystroke.** `Ctrl+S`, `Ctrl+F`, `F3` — one press. **No `Ctrl+K` then `S` sequences.** Ever.
2. **No modifier stacks as the only path.** `Ctrl+Shift+*` never survives legacy terminals (see `KEYMAP.md`), so it's only ever a bonus alias, never the sole way to reach a command.
3. **Modern navigation is first-class and never disabled.** Arrows, `Ctrl`+arrows, `Home`/`End`, `PageUp`/`PageDown`, `Shift`-select, mouse — all standard.
4. **The menu ribbon is the home for the long tail.** Anything without a single-key shortcut lives in the menu (`Esc`/`F9` → File / Edit / Format / View / Help). The menu is *seen and navigated*, not memorized — this is the Microsoft Works idiom, and it's already built and working.
5. **WordStar lives in the brand + the Markdown formatting model** — not in a chord system and not in the diamond. (The WordStar navigation diamond is explicitly rejected: it would consume ~10 of the most valuable single keys — `Ctrl+S`, `Ctrl+A`, `Ctrl+C`, `Ctrl+F`, etc. — and fight every modern convention. We use arrow keys.)

---

## 2. Single-key shortcuts (default profile)

### Navigation & selection — always on
| Key | Action |
|-----|--------|
| `←↑↓→` | Move cursor |
| `Ctrl+←` / `Ctrl+→` | Word left / right |
| `Ctrl+↑` / `Ctrl+↓` | Paragraph up / down |
| `Home` / `End` · `Ctrl+Home` / `Ctrl+End` | Line / document ends |
| `PageUp` / `PageDown` | Scroll |
| `Shift`+motion | Extend selection |
| Mouse | Click / drag / wheel |

### Commands — one keystroke each
| Key | Action |
|-----|--------|
| `Ctrl+N` / `Ctrl+O` / `Ctrl+W` | New / Open / Close file |
| `Ctrl+S` | Save |
| `Ctrl+Q` | **Quit** (restored — no longer a prefix) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| `Ctrl+F` / `Ctrl+R` | Find / Replace |
| `↓` / `Enter` · `↑` | (find bar focused) next match / previous match |
| `Ctrl+A` | Select all |
| `Ctrl+B` | **Bold** — wraps selection in `**…**` |
| `Ctrl+E` | **Emphasis / italic** — wraps selection in `*…*` (`Ctrl+I` is impossible — it's Tab; "E for emphasis" = HTML/Markdown's real name for italic, `<em>`) |
| `Ctrl+PageDown` / `Ctrl+PageUp` | Next / previous tab |
| `Esc` / `F9` | Open menu ribbon |

> **Why not `Ctrl+I` for italic?** In a terminal `Ctrl+I` *is* the Tab key — physically unavailable. Italic uses `Ctrl+E` instead ("emphasis"). The rest of the formatting set lives in the **Format menu** (below).

> Reserved / hazard keys we respect: `Ctrl+I`=Tab, `Ctrl+M`=Enter, `Ctrl+H`=Backspace, `Ctrl+[`=Esc, `Ctrl+J`=LF, `Ctrl+S`/`Ctrl+Q` need flow-control off (Textual raw mode; verify).

---

## 3. The menu ribbon (the long tail — seen, not memorized)

`Esc` or `F9` opens it; `←/→` between menus, `↑/↓` in a menu, `Enter` to pick, first-letter mnemonic to jump. Every command is reachable here on every terminal — this is the guaranteed path.

| Menu | Commands |
|------|----------|
| **File** | New · Open · Close · Close Others · Close All · Save · Save As · Save All · Exit |
| **Edit** | Undo · Redo · Find · Replace · Find Next · Find Previous · **Replace All** · Select All · Duplicate Line · Move Line Up · Move Line Down |
| **Format** *(new — the WordStar `^P` set, as a menu that inserts Markdown)* | Bold `**` *(Ctrl+B)* · Italic `*` *(Ctrl+E)* · Strikethrough `~~` · Inline Code `` ` `` · Link `[]()` · Heading `#` · Blockquote `>` · Bullet List `-` · Numbered List `1.` · Horizontal Rule `---` · Code Fence ` ``` ` |
| **View** | Next Tab · Previous Tab · Soft Wrap · Zen Mode · Theme |
| **Help** | About · Keyboard Shortcuts · Send Feedback |

Menu items show their single-key shortcut in the right column where one exists (e.g. `Bold    Ctrl+B`), so the menu doubles as the cheat sheet.

---

## 4. Replace / Replace All — key commands (this is a keyboard-first app)

When the find bar is focused, single-stroke commands (all terminal-safe):
- **`Enter`** (replace field) → replace one and advance
- **`Ctrl+L`** → **Replace All** ("L" = a**ll**; deliberately *not* `Ctrl+A`, which is Select All everywhere and would nuke the document)
- **`↑` / `↓`** → previous / next match
- **`Esc`** → close

The hint strip lists these in footer format (`KEY  Action`). Replace All also lives in **Edit → Replace All**. No buttons, no function keys, no chords.

---

## 5. Rejected: the WordStar diamond

The WordStar cursor diamond (`Ctrl+E/X/S/D` for arrows, `Ctrl+A/F` word motion, etc.) is **not** adopted, in any profile. It would gobble ~10 of the most useful single keys and collide head-on with `Ctrl+S` (Save), `Ctrl+A` (Select All), `Ctrl+C` (Copy), `Ctrl+F` (Find). **MarkStar uses arrow keys.** WordStar's contribution is the name, the aesthetic, and the Markdown formatting model — nothing about navigation.

---

## 5b. Inline formatting display (approach #1 — style, don't hide)

Always-on, editable, cheap. `**bold**` renders with **bold** applied to the inner text while the `**` markers stay in place but **dimmed to a muted color**; same for `*italic*`, `` `code` ``, `# headings` (brighter/bold), etc. Because no characters are hidden, there is **no source↔screen offset mapping** — the hard part of a live-preview engine is avoided entirely.

Implementation reuses existing machinery: `MarkStarTextArea.get_line()` already applies `stylize` to character ranges for search highlights. Markdown spans use the same path — a per-line scan (regex) produces `(start, end, style)` ranges for bold/italic/code/heading, applied in `get_line`. No new rendering pipeline, no cursor remapping.

Deferred (not now): a read-only full-render toggle (Textual `Markdown` widget), and the Obsidian-style hide-markers-off-cursor-line live preview (that one needs the offset mapping — separate future effort). `Ctrl+P` is left free for whichever of these we add later, if any.

---

## 6. What changes from the current code

- **Delete** all `Ctrl+Shift+*` primary bindings, the tab-key frozensets, and the `MarkStarTextArea` angle-bracket interception hack.
- **Restore** `Ctrl+Q` = Quit; drop the `Ctrl+Shift+P` = menu binding (keep `Esc`/`F9`).
- **Add** a **Format menu** whose items wrap/insert Markdown around the selection; `Ctrl+B` (bold) and `Ctrl+E` (italic/emphasis) as the two formatting single-keys, the rest menu-only.
- **Repoint** Replace All → Edit menu + bar buttons (no hotkey); Save All / Save As / Duplicate / Move-line / Soft-wrap → menus.
- **Tabs** → `Ctrl+PageUp`/`Ctrl+PageDown`.
- **Find next/prev** → `↓`/`Enter` and `↑` while the find bar is focused (replaces the old `Ctrl+Enter` prev and any F-keys).
- Footer hints + menu shortcut column advertise only the portable single keys.
- Tests stay green (command/domain layer unchanged); add Format-menu Markdown-insertion tests.

---

### Settled
- **Formatting single-keys:** `Ctrl+B` bold, `Ctrl+E` italic/emphasis. Everything else (link, strikethrough, code, headings, lists) menu-only. `Ctrl+K` left free.
- **Markdown flavor:** `*italic*` / `**bold**` (CommonMark/GitHub norm).
- **`Ctrl+F` = Find, `Ctrl+R` = Replace** — unchanged, universal. **`Ctrl+H` rejected** for Replace (== Backspace in terminals).
- **Find next/prev = `↓`/`Enter` and `↑`** in the find bar. No function keys.
- **Replace = `Enter`, Replace All = `Ctrl+L`** (find bar focused) + Edit menu. Key-command-first, no buttons, no chords.
- **Diamond rejected.** Arrow keys for navigation. **`Ctrl+P` freed** (inline formatting is always-on, §5b).
- **Inline formatting = approach #1** (style, don't hide; §5b).

Nothing open — ready to implement.

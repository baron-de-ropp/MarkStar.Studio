# MarkStar Studio — Feature Parity Matrix

**Compiled:** 2026-07-21 · against branch `v0.3-file-ux`
**Sources:** [`wordstar-reference.md`](wordstar-reference.md) · [`msworks95-reference.md`](msworks95-reference.md)
**Verified against:** `src/markstar/` at HEAD. **Not** against `README.md` or the keymap docs, both of
which have drifted — see [Documentation drift](#documentation-drift).

---

## How to read this

Every row is a *capability a writer wants*, not a keystroke. **MarkStar today** was checked against the
source, not the documentation: `Have` means the code does it, `Partial` says exactly what is and isn't
there, `Missing` means nothing in `src/markstar/` implements it. **Proposed home** is a single keystroke
or the word *menu only* — MarkStar has no chords and never will, and menu-only is a perfectly respectable
home for a command you use twice a month. **Priority** is P1 (build next), P2 (worth doing), P3 (someday
or never). Rows marked *Reject* explain why a beloved WordStar feature has no sensible Markdown analogue.
Citations follow the reference docs: `[WS4 p.161 (PDF 190)]` is WordStar 4, `[Works §2.1 binary]` is the
Works 4.0 doc with its evidence tag, `[Sawyer]` is the essay digest, `[jstarrc]` is JOE's emulation.

Two things the brief did not know, both confirmed in code and both cheap:

- **There is no go-to-document-start/end.** Textual's `TextArea` binds `home`/`end` to *line* start/end
  and never binds `ctrl+home`/`ctrl+end`; `ScrollableContainer` only scrolls the view. WordStar had this
  on `^QR`/`^QC` [WS4 p.139 (PDF 168)]. Pressing Ctrl+Home in MarkStar today does nothing.
- **Three MarkStar bindings silently shadow real `TextArea` editing commands**: `Ctrl+W` (was
  delete-word-left), `Ctrl+K` (was delete-to-end-of-line), `Ctrl+E` (was cursor-line-end). Accepted
  trades, but they shrink the pool of "free" keys — see [Binding conflicts](#binding-conflicts-and-open-questions).

---

## The matrix

### File lifecycle

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| Opening screen listing every action as one labelled keystroke | Opening Menu / No-File Menu [WS4 p.211 (PDF 238)]; Works Task Launcher, a 3-tab dialog [Works §1.1 manual] | **Have** — `ui/welcome.py`, tabs Recent Files · Projects · New | on launch; Help → Welcome | — |
| Bounded recent-documents list as the primary way back in | Existing Documents tab, with the file browser as the labelled escape hatch [Works §1.2 help] | **Have** — `domain/recent.py`, `prefs.recent_files`, cap 15 | welcome screen | — |
| Recent projects / folders | `L change logged drive/directory` [WS4 p.211 (PDF 238)] | **Have** — `prefs.recent_projects`, cap 5 | File → Recent Projects… | — |
| Open a file by fuzzy name | n/a — WordStar typed a name or pointed at the directory | **Have** — `ui/quick_open.py`, `domain/fuzzy.py` | Ctrl+O | — |
| Open a file by pointing at it in a listing | Cursor onto the name, press Enter [WS4 TG p.48 (PDF 77)] | **Have** — project tree + welcome list | Ctrl+P / welcome | — |
| Live file listing on the *home* screen, with sizes | Directory display is part of the Opening Menu [WS3 p.1-4 (PDF 20)] | **Partial** — welcome shows MRU lists only; the browsable tree lives behind Ctrl+P; no sizes, no free space | keep as is | P3 |
| Change the working directory / project root | `^KL` [WS4 p.161 (PDF 190)] | **Have** — `_set_project_root` | File → Open Folder… | — |
| Create a file by naming one that doesn't exist | Confirm prompt on unknown name | **Have** — typed paths open an empty buffer; tree-focused Ctrl+N prompts and creates | Ctrl+N | — |
| Save and resume at the exact cursor position | `^KS`, recommended as periodic insurance [WS4 p.235 (PDF 262)] | **Have** — Ctrl+S; caret untouched | Ctrl+S | — |
| Save As | Works shipped it with **no accelerator at all** [Works §2.3 binary] | **Have**, menu only | **F12** | P2 |
| Save All | — | **Have**, menu only; prompts per untitled buffer | menu only | — |
| Save-changes prompt on close / quit | `Save changes to %1?` [Works §3.3 binary] | **Have** — `SaveChangesDialog`, Save / Don't Save / Save All / Cancel, driven by `_resolve_dirty` (`app.py:1654`) | automatic | — |
| Abandon all changes since the last save | `^KQ` quit without saving, with confirmation [WS4 p.235 (PDF 262)] | **Missing** — no revert; the only path is close-without-saving then reopen | menu only (File → Revert to Saved) | P2 |
| Automatic `.BAK` of the previous version on every save | Disk file retained as `.BAK` on save [WS4 p.235 (PDF 262)]; Works had an opt-in Create Backup Copy [Works §3.2 help] | **Missing** — the autosave sidecar is crash recovery, not a version; `delete_sidecar` wipes it on every successful save | preference + Tools toggle | P2 |
| Crash recovery of unsaved work | Neither had it — no autosave string anywhere in Works [Works §3.2 unverified] | **Have** — debounced `.autosave` sidecars, `RestoreDialog` on reopen. *MarkStar improves on both.* | automatic | — |
| Warn when the file changed on disk underneath the editor | — | **Missing** — no mtime check on focus or save | automatic | P2 |
| Session restore — reopen the tabs you had open | Neither: WordStar closed to the Opening Menu | **Missing** — `Workspace` is built fresh every launch; only the MRU survives | automatic + preference | **P1** |
| Rename a file without leaving the editor | `^KE` [WS4 p.161 (PDF 190)] | **Missing** | menu only (tree context) | P2 |
| Delete a file without leaving the editor | `^KJ`, wildcards accepted [WS4 p.161 (PDF 190)] | **Missing** | menu only (tree context) | P2 |
| Copy a file without leaving the editor | `^KO` [WS4 p.161 (PDF 190)] | **Missing** | menu only | P3 |
| Run a shell command without leaving the editor | `^KF` / `R` at the Opening Menu [WS4 p.256 (PDF 283)] | **Missing** | menu only | P3 |
| Read-only / protected file, with modifying commands hidden from the menus | `C protect a file`; protected menus redrawn without the dangerous commands [WS4 p.187 (PDF 214)] | **Missing** | menu only | P3 |
| Quit | `^KX` / `X` [WS4 p.235 (PDF 262)]; "Exit Works" [Works §3.4 binary] | **Have** — Ctrl+Q, walks every dirty buffer | Ctrl+Q | — |

### Navigation

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| Character and line motion | The `^E ^S ^D ^X` diamond [WS4 p.139 (PDF 168)] | **Have** — arrow keys (diamond deliberately rejected) | arrows | — |
| Word left / right | `^A` / `^F` [WS4 p.139 (PDF 168)] | **Have** — Ctrl+←/→, `domain/motion.py` | Ctrl+←/→ | — |
| Paragraph up / down | — | **Have** — Ctrl+↑/↓. *MarkStar original.* | Ctrl+↑/↓ | — |
| Line start / end | `^QS` / `^QD` [WS4 p.139 (PDF 168)] | **Have** — Home / End (Textual `TextArea`) | Home / End | — |
| **Beginning / end of document** | `^QR` / `^QC`, "directly to" [WS4 p.139 (PDF 168)] | **Missing** — `TextArea` binds neither `ctrl+home` nor `ctrl+end`; `ScrollableContainer`'s `home`/`end` are shadowed by `TextArea`'s line motions. Verified in `textual 8.2.8` | **Ctrl+Home / Ctrl+End** | **P1** |
| Scroll by screen | `^R` / `^C`, also PgUp/PgDn [WS4 p.236 (PDF 263)] | **Have** — PageUp / PageDown | PgUp/PgDn | — |
| **Go to a line number** | `^QI` — page in documents, *line* in nondocuments [WS4 p.166 (PDF 195)]; jstar made it line [jstarrc]; Works: Edit → Go To, `Ctrl+G` **and** `F5` [Works §2.1 binary] | **Missing** — nothing bound. `_cursor_line_col()` exists at `app.py:1227` with **zero callers** | **Ctrl+G** (after moving spell-suggest to F8) | **P1** |
| Jump to a heading / document outline | Nearest analogues: `^QI` page jump, plus the `T` table-of-contents generator [WS4 p.174 (PDF 201)] | **Missing** — no outline model at all | **F4** (outline picker, same idiom as Quick Open) | **P1** |
| Return the cursor to where it was before the last command | `^QP` — "the single most-loved command in the set" [WS4 p.166 (PDF 195)]; [Sawyer] | **Missing** — no position history of any kind | **F2** | **P1** |
| Full backward *and forward* position ring | jstar generalised `^QP` with `^K=` forward [jstarrc] | **Missing** | F2 back; forward unassigned — see open questions | P2 |
| Return to the last find match / last marked block | `^QV` [WS4 p.166 (PDF 195)] | **Missing** | folds into the position ring | P3 |
| Ten numbered place markers, set and jumped to by digit | `^K0`–`^K9` set, `^Q0`–`^Q9` go; session-only [WS4 p.218 (PDF 245)] | **Missing** | menu only + the F4 picker — digits need a prefix key, which is forbidden | P2 |
| Persist markers across sessions | WordStar explicitly did **not** [WS4 p.218 (PDF 245)] | **Missing** — a deliberate upgrade if built | with markers | P3 |
| Scroll by line while the cursor stays put in the text | `^W` / `^Z` [WS4 p.236 (PDF 263)] | **Missing** — mouse wheel only, no key | menu only / skip | P3 |
| Continuous self-propelled scroll with live speed control | `^QW` / `^QZ`, digits 0–9 set speed [WS4 p.236 (PDF 263)] | **Missing** | skip — charming, near-zero value | P3 |
| Top / bottom of the visible screen | `^QE` / `^QX`, Home/End [WS4 p.139 (PDF 168)] | **Missing** | skip | P3 |
| Jump to the next/previous occurrence of a single character | `^QG` / `^QH` [WS4 p.165 (PDF 194)] | **Missing** | skip — Find covers it | P3 |
| Next / previous document | Windows MDI supplied `Ctrl+F6` [Works §2.3 binary] | **Have** — Ctrl+PgUp / Ctrl+PgDn | Ctrl+PgUp/PgDn | — |

### Selection and blocks

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| Select all | `Ctrl+A` [Works §2.1 binary] | **Have** — Ctrl+A (overrides `TextArea`'s line-start) | Ctrl+A | — |
| Shift+motion selection, drag, double-click word, triple-click line | — | **Have** — `MarkStarTextArea.on_click` handles chain ≥ 2 | mouse / Shift | — |
| Cut / copy / paste, bridged to the OS clipboard | Works shipped *both* CUA generations [Works §2.1 binary] | **Have** — Ctrl+X/C/V plus native `wl-copy`/`xclip`/`pbcopy`/`clip` and OSC 52 | Ctrl+X/C/V | — |
| **Mark a block's start and end as independent, durable acts** — keep writing for an hour in between | `^KB` / `^KK`; markers are positions in the text, not a fragile highlight — [Sawyer]'s single biggest claim for WordStar | **Missing** — selection is a live `Selection` destroyed by the next keystroke | menu only | P2 |
| Jump to the start / end of the marked block | `^QB` / `^QK` [WS4 p.166 (PDF 195)] | **Missing** | with block markers | P3 |
| Copy / move / delete the marked block | `^KC` / `^KV` / `^KY` [WS4 p.122 (PDF 151)] | **Have** in modern form (clipboard) | Ctrl+X/C/V | — |
| Hide block highlighting as an accidental-edit interlock | `^KH`; WordStar *refuses* block ops while hidden [WS4 p.123 (PDF 152)] | **Missing** | skip — no modern analogue | P3 |
| **Write the marked block out to a new file** | `^KW`; the block stays in the working file [WS4 p.161 (PDF 190)]. "The clipboard is the filesystem" [Sawyer] | **Missing** | menu only (File → Write Selection to File…) | **P1** |
| **Insert another file into the document at the cursor** | `^KR`, for boilerplate and reassembly [WS4 p.123 (PDF 152)] | **Missing** — `![[include]]` is the *reference* form (resolved only on Compile); there is no *flatten now* | menu only (Insert → File at Cursor…) | **P1** |
| Insert the last-saved version of the current file into itself | `^KR` on the current file [WS4 p.123 (PDF 152)] | **Missing** | skip | P3 |
| Convert the selection to upper / lower case | `^K'` / `^K"` [WS4 p.126] | **Missing** | menu only (Edit → Change Case) | P2 |
| Total the numbers inside a selection | `^KM` block math; `Esc =` inserts the result [WS4 p.120 (PDF 149)] | **Missing** — real value for TTRPG price/stat tables | menu only | P3 |
| Filter the selection through an external command | jstar `^K/` [jstarrc] | **Missing** — powerful in Markdown (sort a list, run a formatter) | menu only | P3 |
| Mark the word under the cursor in one keystroke | jstar `^KT` [jstarrc] | **Partial** — double-click only, no key | skip | P3 |
| Rectangular / column selection, column replace | `^KN` / `^KI`, for table surgery [WS4 p.129 (PDF 158)] | **Missing** | *Reject* — see rejected list | — |

### Find and replace

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| Find a string, leaving the caret at the match | `^QF` [WS4 p.162 (PDF 191)]; `Ctrl+F` [Works §2.1 binary] | **Have** — Ctrl+F, live match count badge, soft highlight of every hit | Ctrl+F | — |
| Find and replace with per-occurrence confirmation | `^QA`, interactive by default [WS4 p.162 (PDF 191)]; `Ctrl+H` [Works §2.1 binary] | **Have** — Ctrl+R; Enter in the replace field replaces one and advances | Ctrl+R | — |
| Replace all | `^QA` with `G`/`N` [WS4 p.163 (PDF 192)] | **Have** — Ctrl+L in the find bar + Edit menu; whole document only | Ctrl+L (in bar) | — |
| **Repeat the last find from the text, without the find bar focused** | `^L` [WS4 p.162 (PDF 191)]; `Shift+F4` [Works §2.2 inferred] | **Missing** — ↑/↓/Enter step only while the bar has focus; dismiss the bar and there is no "again" key | **F3** | **P1** |
| **Whole-words-only matching** | `W` option. [Sawyer]'s specific complaint against WordPerfect: it matched `can` inside *American* | **Missing** — `domain/search.py` is a bare `str.find` | Edit menu checkbox toggle | **P1** |
| **Case-sensitive matching** | `U` option = *ignore* case, i.e. case-sensitive was the default [WS4 p.163 (PDF 192)] | **Missing** — `find_next`/`find_all` take `case_sensitive`, but `ui/find_controller.py` **never passes it**; every search is `.lower()`-folded | Edit menu checkbox toggle | **P1** |
| Regular expressions | Not a WordStar feature — only the opt-in `?` wildcard [WS4 p.163 (PDF 192)] | **Missing** | Edit menu checkbox toggle | P2 |
| Backward search | `B` option [WS4 p.163 (PDF 192)] | **Partial** — ↑ steps backward through hits; no persistent backward mode | keep as is | P3 |
| Replace from the cursor to the end / nth occurrence only | `R` and *n* options [WS4 p.163 (PDF 192)] | **Missing** — Replace All is whole-document, unbounded | skip | P3 |
| **Find across every file in the project** | Not in either product — WordStar searched one file at a time | **Missing** | menu only, results in a Quick-Open-style picker | **P1** |
| Search for line endings and control characters via a literal-next prefix | `^P` prefix; `^P^M^P^J` matches a hard return [WS4 p.162 (PDF 191)] | **Missing** | folds into regex | P3 |
| Reflow each affected paragraph after replacement | `A` option [WS4 p.163 (PDF 192)] | **Missing** — depends on reflow existing at all | skip | P3 |
| Interrupt a running find or replace | `^U` [WS4 p.162 (PDF 191)] | **Missing** — irrelevant at current document sizes | skip | P3 |
| Configurable default search options | WSCHANGE [WS4 p.165 (PDF 194)] | **Missing** | persist the Edit-menu toggles in `config.toml` | P2 |

### Formatting and layout

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| Bold / italic | `^PB` / `^PY` [WS4 p.219 (PDF 246)]; `Ctrl+B` / `Ctrl+I` [Works §2.2 inferred] | **Have** — Ctrl+B / **Ctrl+E** (Ctrl+I is physically Tab [Works §6.1]) | Ctrl+B / Ctrl+E | — |
| Strikethrough, inline code, link, heading, blockquote, lists, rule, fence | `^PX`, `^PS`, … [WS4 p.219 (PDF 246)] | **Have** — Format menu, all menu-only, all idempotent toggles | Format menu | — |
| Never create an unbalanced marker pair | WordStar warned that deleting half a pair leaks the effect to end-of-document [WS4 TG p.58 (PDF 87)] | **Have** — `domain/markdown.toggle_emphasis` strips or wraps atomically | automatic | — |
| Toggle display of inline formatting marks | `^OD` [WS4 p.219 (PDF 246)] | **Have** — View → Formatting Preview; markers dim, never hidden, so columns stay 1:1 | menu only | — |
| Preview mode that hides markup and locks the buffer | `^OP`, switches to protected menus while previewing [WS4 p.219 (PDF 246)] | **Missing** — deferred in the design spec | menu only | P3 |
| **Reflow the current paragraph to a margin** | `^B` align paragraph [WS4 p.116 (PDF 145)] | **Missing** — soft wrap only; nothing hard-wraps text | menu only (Format → Reflow Paragraph) | P2 |
| Reflow from the cursor to end of document, interruptibly | `^QU`, `^U` stops it [WS4 p.116 (PDF 145)] | **Missing** | menu only | P3 |
| Mark a region as never-reflow | `.AW off` protects tables [WS4 p.151 (PDF 180)] | **Have** by construction — fenced code is already excluded from styling and spellcheck, and nothing reflows | automatic | — |
| Toggle word wrap | `^OW` [WS4 p.257 (PDF 284)] | **Have** — View → Soft Wrap, persisted | menu only | — |
| Writing measure / margin control | `^OL` / `^OR`, default cols 1–65 [WS4 TG p.35 (PDF 64)] | **Partial** — `prose_width` (default 120) and `center_text` are config values; Center Text is a menu toggle, width is hand-edited TOML only | menu only (Format → Writing Measure…) | P3 |
| List indent / outdent | `^OG` temporary indent [WS4 p.343 (PDF 372)]; `Ctrl+M` unrepresentable, Tab recommended [Works §6.1] | **Missing** — Tab inserts a literal tab; no list awareness | Tab / Shift+Tab, in list context | P2 |
| Non-breaking space | `^PO` binding space [WS4 p.116 (PDF 145)] | **Missing** | menu only | P3 |
| **Insert today's date / current time** | `Esc @` / `Esc !` shorthand [WS4 p.238 (PDF 265)]; Insert → Date and Time [Works §4 binary] | **Missing** — note the registry already reserves an empty **Insert** menu slot (`registry.menu_names`) | menu only (Insert → Date) | P2 |
| User-defined text macros | 36 `Esc`+char shorthands [WS4 p.238 (PDF 265)]; Works Easy Text [Works §4 binary] | **Missing** | menu only | P3 |
| Transpose adjacent words | `Esc T` [WS4 p.238 (PDF 265)] | **Missing** | menu only | P3 |
| Insert / overtype toggle | `^V` or `Ins` [WS4 p.177] | **Missing** | menu only | P3 |
| Split the line at the cursor without moving it | `^N` [WS4 TG p.93 (PDF 122)] | **Missing** | skip | P3 |
| Delete word / to line start / to line end | `^T`, `^QY`, `^Q Del` [WS4 p.145] | **Partial** — `TextArea` supplies `alt+delete` (word right), `ctrl+u` (to line start), `ctrl+backspace`; **`Ctrl+W` (word left) and `Ctrl+K` (to line end) are shadowed** by Close and StarBot | document what survives | P2 |
| Move / duplicate line | — | **Have** — Edit menu, menu only | menu only | — |
| Undo / redo | `^U` unerase, one slot, 500 chars [WS4 p.254 (PDF 281)]. **Works had no redo at all** [Works §2.2] | **Have** — real op-based undo stack, Ctrl+Z / Ctrl+Y. *Improves on both.* | Ctrl+Z / Ctrl+Y | — |

### Output and export

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| Include another file at output time, file chaining | `.FI`; a command file of nothing but `.FI` lines prints a whole multi-file manuscript with continuous page numbers [WS4 p.209 (PDF 236)] | **Have** — `![[name]]` + File → Compile…, recursive, cycle-safe, missing includes reported as HTML comments (`domain/includes.py`) | menu only | — |
| Build a whole manuscript from a list of component files | as above | **Have** — a master file of includes | menu only | — |
| **Export to DOCX / PDF / ODT / HTML** | `P print a file` was the output path [WS4 p.211 (PDF 238)]; Works `Ctrl+P` [Works §2.1 binary]. Design spec §12 lists Pandoc export as roadmap | **Missing** — Compile produces only `.compiled.md` | **F5** (Export…) — Ctrl+P is the project panel by Baron's decision [Works §6.4] | **P1** |
| Print | `^KP` print while editing [WS4 p.222]; `Ctrl+P` [Works §2.1 binary] | **Missing** | F5, same dialog | P2 |
| **Inline author comments, visible while editing, stripped on output** | `..` or `.IG`; a note you cannot fail to see during revision, unlike a hidden annotation [WS4 p.134 (PDF 163)]; [Sawyer] | **Missing** — `<!-- … -->` already works in every renderer, but `domain/markdown.markdown_spans` doesn't style it and nothing inserts one | menu only (Insert → Comment) + a span rule | **P1** |
| Table of contents | `T` at the Opening Menu [WS4 p.174 (PDF 201)] | **Missing** | menu only — free once the F4 outline model exists | P2 |
| Index, from inline entry marks | `^PK` / `.IX`, with exclusion lists [WS4 p.174 (PDF 201)] | **Missing** — real value for a TTRPG book, expensive to build | menu only | P3 |
| Headers, footers, page numbering, page margins | `.HE` `.FO` `.PN` `.PO` `.MT` `.MB` [WS4 p.149 (PDF 178)] | **Missing** | *not editor commands* — YAML front-matter fields consumed by the exporter | P2 |
| Force a page break | `.PA` [WS4 p.151 (PDF 180)] | **Missing** | export-time directive, not a key | P3 |
| Conditional page break, keep *n* lines together | `.CP` [WS4 p.151 (PDF 180)] | **Missing** | *Reject* — no Markdown analogue | — |
| Mail merge / templating from a data file | MailMerge, `M` at the Opening Menu [WS3 p.1-3 (PDF 19)] | **Missing** | menu only | P3 |
| Save and export in one command | `^PrtSc` [WS4 p.235 (PDF 262)] | **Missing** | folds into F5 | P3 |

### Assistance and help

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| **A real help screen** | `J help` on the Opening Menu; `^J` at any help level; `^J?` explains the screen layout, `^J.` explains dot commands [WS4 p.172 (PDF 199)]. Works: a docked help pane *next to* the document [Works §5 manual] | **Missing** — all three Help items are `self.notify()` toasts (`app.py:2797–2808`); Keyboard Shortcuts dumps the registry into an 8-second toast | **F1** (with an emulator caveat — see open questions) | **P1** |
| Persistent status-line hint on how to get help and how to exit | jstar's `-rmsg` keeps `Ctrl-J for help` in the status line permanently [jstarrc] | **Partial** — `_SUPPORT_HINTS` is a one-item list, `Esc Menu` (`app.py:913`) | add a help hint | P2 |
| Contextual help for one command from its menu | `^J` then the command letter [WS4 TG p.20 (PDF 49)] | **Missing** | menu only | P3 |
| Progressive help levels 3 → 0, stripping menus then prompts then the status line | [WS4 p.171 (PDF 198)]; [Sawyer]'s point 8 | **Partial** — Zen mode is a one-step version of the same instinct | keep Zen | P3 |
| Menus that appear only when you hesitate after a prefix key | Help level 2 timing disclosure [WS4 p.120 (PDF 149)] | **Missing** | *Reject* — MarkStar has no prefix keys to hesitate after | — |
| **Word, line and character count for the document** | `WC` utility, run via `R` or `^KF` [WS4 p.255 (PDF 282)]; Works Tools → Word Count, no accelerator [Works §4 binary] | **Partial** — the footer shows characters + words always-on, but drops the character count below 92 columns and everything but words below 66 (`app.py:87–88`); no line count, no selection count, no dialog | menu only (Tools → Word Count…) | **P1** |
| **Word count aggregated across a multi-file manuscript** | The manual's own example totals `chapter1/2/3.doc` [WS4 p.255 (PDF 282)] | **Missing** | same dialog — count the include graph, then the project | **P1** |
| Character count from start of file to the cursor, as a progress indicator | `^Q?` [WS4 p.255 (PDF 282)] | **Missing** | fold into the Word Count dialog | P3 |
| Spell-check the whole document | `^QL` from the cursor [WS4 TG p.51 (PDF 80)]; `F7` [Works §2.1 binary] | **Have** — Tools → Spelling… walks every misspelling; F7 toggles live underlining | F7 | — |
| Spell-check the word at the cursor | `^QN` [WS4 TG p.51 (PDF 80)] | **Have** — Ctrl+G, suggestion popup with Add / Ignore | → **F8** (frees Ctrl+G) | P2 |
| Personal dictionary alongside the main one | Two dictionaries [WS4 TG p.51 (PDF 80)] | **Have** — `prefs.spell_added`, plus a session ignore-set | automatic | — |
| Look up a typed word without inserting it | `^QO` [WS4 TG p.51 (PDF 80)] | **Missing** | menu only | P3 |
| Thesaurus | Works `Shift+F7` [Works §2.1 binary] | **Missing** — genuinely useful for a working writer; needs a data source, or StarBot | menu only | P2 |
| Calculator while editing | `^QM` [WS4 p.120 (PDF 149)] | **Missing** | skip | P3 |
| AI editorial assistant | — | **Have** — StarBot, Ctrl+K: agentic, project tools, propose-approve edit cards, saved transcripts. *MarkStar original.* | Ctrl+K | — |
| Configurable defaults, with an in-app settings UI | Hundreds of WSCHANGE settings [Sawyer]; Works Tools → Options… [Works §4 binary] | **Partial** — `config.toml` is hand-editable and covers theme, wrap, width, spell, autosave, MRU; only some are reachable from a menu; `prose_width` and `min_panel_width` are TOML-only | menu only (Tools → Options…) | P2 |

### Display and status

| Feature | What WordStar / Works did | MarkStar today | Proposed home | Pri |
|---|---|---|---|---|
| **Line : column in the status bar** | Status line shows Page, Line, Column (Line and Column in nondocuments) [WS4 p.147 (PDF 176)]. `PROSE_V0.1_DESIGN_SPEC.md` §5.9 promises "Word count · L:C · dialect" | **Missing** — the footer renders `N characters │ N words │ CommonMark`. `_cursor_line_col()` is written and has no callers (`app.py:1227`) | no key — just render it | **P1** |
| Word count in the status bar | — | **Have** — always-on, degrades on narrow terminals | automatic | — |
| Per-line status gutter distinguishing hard endings from soft wraps, flagging structural lines | The flag column: `<` `P` `F` `^` `+` `.` `:` `?` [WS4 p.166 (PDF 195)] — "a genuinely good idea that modern editors dropped" | **Missing** — the Markdown analogue would flag hard-wrapped lines, headings, include tokens, over-long lines | menu only toggle | P3 |
| Toggle display of invisible characters | `^OB` soft spaces [WS4 p.343 (PDF 372)]; Works View → All Characters [Works §4 binary] | **Missing** | menu only | P3 |
| Redraw the screen on demand | `^\` [WS4 p.128 (PDF 157)] | **Missing** | Ctrl+L (free at app level; already Replace All *inside the find bar*) | P3 |
| Toggle the file listing on and off | `F` at the Opening Menu [WS3 p.1-4 (PDF 20)] | **Have** — Ctrl+P, three states: open+focus / focus / close | Ctrl+P | — |
| Reveal the active file in the listing | — | **Have** — `_reveal_active_file` on open and tab switch; tree refreshes on focus | automatic | — |
| Themes | Ribbon colours and print wheels — hardware-era, excluded | **Have** — View → Theme… with live preview, Esc reverts; terminal background synced via OSC 11 | menu only | — |
| Distraction-free mode | Help level 0 removed even the status line [WS4 p.171 (PDF 198)] | **Have** — Zen mode empties the chrome without moving the prose frame | menu only | — |
| Report memory or resource use | `?` at the Opening Menu [WS4 p.186 (PDF 213)] | **Missing** | *Reject* — hardware-era | — |
| Menus reachable entirely by keyboard | Eight top-level menus, every item `Alt`+letter [Works §4 binary] | **Have** — Esc / F9, ←/→ across menus, first-letter jump for File/Edit/View/Help only | extend mnemonics to Format/Tools/Project | P3 |

**Row count: 129** — File lifecycle 23 · Navigation 18 · Selection and blocks 15 · Find and replace 14 ·
Formatting and layout 20 · Output and export 12 · Assistance and help 16 · Display and status 11.

---

## Top 10 recommendations

Weighted for a writer who ships TTRPG books and long-form video scripts out of a multi-file project —
not for programmer conveniences.

**1. Export to DOCX / PDF / HTML — F5.** Right now the only thing MarkStar can produce is more Markdown.
Every book Baron publishes and every script he hands to an editor has to leave this program in a format
somebody else can open, which means the last mile happens in another tool every single time. Compile
already resolves the include graph into one clean buffer, so the build is: hand that string to Pandoc (or
a bundled fallback), add a target picker, and thread YAML front-matter through as title/author/geometry.
WordStar's answer to this was `.FI` plus a printer [WS4 p.209 (PDF 236)]; the modern answer is a subprocess.

**2. Word count — document, selection, and across the whole manuscript — Tools menu.** A working author's
single most-asked question is "how long is this thing," and MarkStar answers it only for the file
currently in the buffer, in a footer that silently amputates itself below 92 columns. The WordStar manual's
own worked example is totalling three chapter files into a book length [WS4 p.255 (PDF 282)] — exactly the
MarkStar case. Build: one dialog, three numbers (document / selection / project or include-graph), reusing
`Document.word_count()` and `domain/includes` to walk the tree. Half a day.

**3. Session restore.** Close MarkStar with eleven chapter files open and it forgets all of them; you get
one blank buffer and a recent-files list to rebuild from by hand. For a book project this is the single
most-felt piece of daily friction, and it is the cheapest P1 here: serialise `[path, cursor, scroll]` per
tab plus the active index into `config.toml` on exit, restore it on launch when no CLI path was given.
Neither WordStar nor Works had it — both closed to their home screen — so this is pure upgrade.

**4. Go to line, and go to top/bottom of document.** Two separate gaps that feel like one. `Ctrl+G` should
be Go To Line (its CUA-correct home [Works §2.1 binary]) once spell-suggest moves to F8; `_cursor_line_col()`
is already written and waiting at `app.py:1227`. Separately, **Ctrl+Home and Ctrl+End do nothing at all**
today — Textual's `TextArea` binds neither — so there is no way to reach the top of a 4,000-line manuscript
except by holding PageUp. WordStar considered `^QR`/`^QC` so basic it put them in the first table of the
manual [WS4 p.139 (PDF 168)]. This is an afternoon.

**5. Find that behaves the way a writer expects — whole-word and case-sensitive.** MarkStar's search is a
bare `str.find` on a `.lower()`ed haystack: searching `Ash` in a setting book matches *ashes*, *cash*, and
*Ashe*, with no way to say otherwise. Sawyer's specific indictment of WordPerfect was exactly this
[Sawyer]; WordStar's `W` and `U` options fixed it in 1981 [WS4 p.163 (PDF 192)]. `domain/search.py`
already takes a `case_sensitive` parameter that `find_controller.py` never passes. Add whole-word and
regex alongside it, expose all three as checkmarked Edit-menu toggles (the Spellcheck toggle already
demonstrates the pattern), and show the active options in the find bar.

**6. Find Next as a key you can press from the text — F3.** Today, stepping through matches requires the
find bar to hold focus; the moment you Esc back to writing, "again" is gone and you must reopen and
retype. WordStar spent a whole top-level key on this (`^L`) precisely because revision is a loop of
find-edit-find [WS4 p.162 (PDF 191)]. One binding, one call to `FindController.find("next")` that opens
the bar if it isn't open.

**7. Project-wide find.** A supplement lives in thirty files; the phrase you need to rename lives in four
of them and you don't know which. Right now the only way to find out is to open each file and press
Ctrl+F. Neither reference product could do this — WordStar searched one file at a time — so this is
MarkStar deciding to be better than its ancestor at the thing its ancestor was for. Build: walk
`list_project_files()` (already written, already threaded in Quick Open), run `find_all` per file, show
hits in a picker that opens the file at the match. Reuse three existing modules.

**8. A jump-to-heading outline — F4.** WordStar gave writers ten numbered place markers because a novelist
lives between chapter three and the outline at the end of the file [WS4 p.218 (PDF 245); Sawyer]. MarkStar
can't inherit the mechanism — `^K3`/`^Q3` are chords — but it doesn't need to, because Markdown already
publishes its own structure: headings. One key opens a filterable list of every heading in the buffer;
Enter jumps. It reuses the Quick Open picker wholesale, it gives you table-of-contents generation almost
free afterwards, and for a rulebook with sixty section headers it replaces the place-marker feature
entirely and more honestly.

**9. Return to previous position — F2.** `^QP` is the command WordStar users named first, forty years on:
you jump to check a stat block, then get put straight back where you were writing [WS4 p.166 (PDF 195)].
MarkStar has no positional memory of any kind — every jump is one-way, and after Go To Line and the
outline picker land, one-way jumps become the dominant way you move. Push `(tab, line, col)` onto a
bounded ring on every non-adjacent motion, step back on F2. jstar's `^K=` forward-step [jstarrc] can come
later.

**10. Inline author comments that are visible while you write and gone on export.** Sawyer singles this
out: a note beginning `..` cannot be overlooked during revision the way a hidden annotation can
[WS4 p.134 (PDF 163)]. MarkStar is 90% of the way there for free — `<!-- TK: verify the encumbrance rule -->`
is already valid Markdown that every renderer strips — but the editor renders it as ordinary grey text
with no visual distinction and offers no way to insert one. Add a comment span rule to
`domain/markdown.markdown_spans` (a handful of lines, the machinery is identical to the existing include
token) plus an Insert → Comment item. Cheapest item on this list, and it directly serves the draft-notes
habit that TK-markers and revision passes run on.

---

## Deliberately rejected

| WordStar feature | Why MarkStar should not adopt it |
|---|---|
| **The cursor diamond** (`^E ^S ^D ^X`, `^A` `^F`) | Consumes ~10 of the most valuable single keys — including `Ctrl+S` (Save), `Ctrl+A` (Select All), `Ctrl+F` (Find) — to reimplement keys the keyboard already has. Sawyer's argument was home-row economy on a 1981 terminal without reliable arrow keys [Sawyer]; that premise is gone. Already rejected in `MARKSTAR_KEYMAP.md` §5 and correct. |
| **Two-key chords / prefix menus** (`^K`, `^Q`, `^O`, `^P`) | Baron's hard constraint, and the right one. The entire Works thesis is that a key means one thing regardless of what preceded it [Works §5.4]. Chords are also what makes the "hesitate and the menu appears" trick necessary — remove chords and you remove the need. |
| **Dot commands** (`.LM`, `.RM`, `.HE`, `.PA`, …) | A pre-Markdown markup language embedded in the text. Markdown *is* the markup language; layout belongs in YAML front matter consumed at export, not in a second syntax the renderer would have to be taught to strip. |
| **Print controls as paired inline toggles** (`^PB` … `^PB`) | WordStar warned that deleting half a pair leaks the effect to end-of-document [WS4 TG p.58 (PDF 87)]. Markdown's delimiters are the same idea done safely, and `toggle_emphasis` already guarantees balance. Solved problem; don't reintroduce it. |
| **Column / rectangular blocks and column replace** (`^KN`, `^KI`) | Existed for table surgery in a fixed-pitch world [WS4 p.129 (PDF 158)]. Markdown tables are pipe-delimited text, not columns of cells; rectangular selection would fight soft wrap and the design spec already excludes column select. |
| **Ruler line, tab stops, decimal tabs, justification, line spacing, hyphen help, soft hyphens** (`^OT`, `^OI`, `^OJ`, `^OS`, `^OH`, `^OE`) | All describe the geometry of a printed page. Markdown has no margins, no justification, no line height and no line-end control — those decisions belong to whatever renders the export. Adopting them would mean inventing state the file format cannot carry. |
| **`^U` as one key for undo, unerase, and universal interrupt** | Overloaded because 1981 had no undo stack. MarkStar already has real op-based undo/redo; the "erase, move, unerase" move-by-cut idiom is just cut-and-paste. Splitting these is the correct modernisation, as the reference doc itself recommends [WS4 p.254 (PDF 281)]. |
| **Help levels 3 → 0 as a four-rung ladder** | The progressive-disclosure instinct is right and Zen mode already captures the useful end of it. Four modes of the same UI is configuration surface, not a feature; the menu is always one Esc away regardless. |
| **Timing-based menus** (hesitate after `^K` and the menu appears) | The best idea in the WordStar interface [WS4 p.120 (PDF 149)] — and inapplicable, because it exists to soften chords and MarkStar has none. There is no prefix key to hesitate after. |
| **Wildcard `?` matching** | Superseded by regex, which is the same capability without a mode toggle that changes what a literal `?` means. |
| **Conditional page breaks, memory-usage reporting, drive letters, printer pitch** | Hardware-era. Already excluded by the reference doc's own inventory. |

---

## Binding conflicts and open questions

Questions, not decisions. Each needs Baron's call before any of it is built.

**1. Move spell-suggest to F8 to free Ctrl+G for Go To Line?** The msworks doc's preferred option
[Works §6.4]: F8 sits next to F7 (spellcheck), so the two spelling commands pair mnemonically, and
`Ctrl+G` returns to its CUA-correct meaning. The alternative is keeping Ctrl+G on spell-suggest and
putting Go To Line on Ctrl+L. Which?

**2. Print / Export on F5?** [Works §6.4] proposes it because Ctrl+P is fixed on the project panel by
your decision. F5 is free, terminal-safe, and single-key. Any objection to spending a function key on
the command that turns a manuscript into a deliverable?

**3. Save As on F12?** Works shipped Save As with *no accelerator at all* [Works §2.3 binary]; F12 is the
Word convention of the era and is free here. Worth a key, or leave it menu-only where it already lives?

**4. F3 for Find Next, or for document cycling?** These collide. [Works §6.4] proposes `F3` / `Shift+F3`
as terminal-safe fallbacks for `Ctrl+PgUp/PgDn` tab switching; this document proposes F3 for Find Next
(the near-universal editor meaning, and WordStar's `^L`). Both cannot have it. Sub-question: do
`Ctrl+PgUp/PgDn` actually work in your terminal? If yes, the fallback is unnecessary and F3 is free for
Find Next.

**5. Forward-step in the position ring — what key?** F2 for *back* is uncontroversial. Forward has no
obvious home: `Shift+F2` is only *mostly* portable (`KEYMAP.md` §3 rates Shift+F-keys as semi-reliable,
unlike `Ctrl+Shift+letter` which is impossible), and `Ctrl+T` is free but unmnemonic. Or ship back-only
and see whether you ever miss forward — jstar added it as an extra, not a core [jstarrc].

**6. F1 for Help?** `KEYMAP.md` §3 lists F1 as "stolen by some emulators." It is also the one key every
user of a 1995-era application will try first. Bind it and accept that it fails in a minority of
terminals, or put Help somewhere less obvious?

**7. Ctrl+L — screen redraw, or leave it spare?** It is free at app level, and redraw-on-Ctrl+L is a
universal terminal convention. But Ctrl+L is already Replace All *inside the find bar*, so the same
physical key would mean two things in two focus contexts. Acceptable, or confusing?

**8. Ctrl+T is the only genuinely free Ctrl+letter left.** Every other one is taken by MarkStar, taken by
`TextArea`, or physically impossible. Worth noting before it gets spent casually. (Also: on macOS/BSD
`Ctrl+T` is the tty `VSTATUS` character, safe only in raw mode — the same caveat `KEYMAP.md` §3 already
records for `Ctrl+S`/`Ctrl+Q`/`Ctrl+Z`.)

**9. Three `TextArea` editing commands are silently shadowed.** `Ctrl+W` was delete-word-left, `Ctrl+K`
was delete-to-end-of-line, `Ctrl+E` was cursor-line-end. All three are now Close, StarBot and Italic. The
trades look right, but the deleted capabilities are undocumented anywhere and a writer coming from another
terminal editor will hit them. Restore any of them elsewhere, or just document the loss?

**10. Should Ctrl+N reopen the welcome screen instead of making a blank buffer?** [Works §6.4] proposes it,
citing the shipped Works string: *"Displays Task Launcher for access to documents, templates, and
TaskWizards"* [Works §1.4 binary] — New did not silently spawn Document2. MarkStar's Ctrl+N currently
creates an untitled buffer (or, with the tree focused, prompts for a name). Change, or keep?

**11. Adopt the Works `##` dialog house style?** Statement, then consequence, then remedy — never a bare
error [Works §3.3 binary]. MarkStar's dialogs are already close (`ConfirmDialog` gives a reason line);
the notifications are not. Cheap, and it is the most characteristic texture of the Works experience.

**12. Two commands exist in the code but are unreachable.** `cmd_toggle_mouse_capture` and
`cmd_cycle_theme` are implemented and registered nowhere — no menu row, no key, zero references. Worse,
the mouse toast tells the user "View menu re-enables" (`app.py:2386`), which is false: there is no such
menu item. Register them, or delete them?

---

## Documentation drift

Everything below describes something the code does not do. `README.md` and `docs/MARKSTAR_KEYMAP.md` were
partially updated this session and are the closest to true; the other three are stale enough to actively
mislead.

**`README.md`** — mostly accurate on keys after this session's edits, but:
- Status line still reads *"v0.1 in progress — P0–P2 (shell, menus/find, multi-file tabs + motion)"*. The
  repo has shipped tabs, spellcheck, themes, autosave, StarBot and the whole v0.3 file-UX layer.
- *"pytest # 30 tests"* — there are **52 test files**.
- The Docs section links only `PROSE_V0.1_DESIGN_SPEC.md`, which is the most drifted document in the repo.
- The menu-only list omits Recent Projects, Include File, Compile, Center Text, Formatting Preview,
  Autosave, Spelling…, Theme…, and every Project/StarBot and Help command.
- Ctrl+X / Ctrl+C / Ctrl+V are implemented (with an OS-clipboard bridge) and appear nowhere in the table.

**`docs/MARKSTAR_KEYMAP.md`** — §7 (the v0.3 file-lifecycle layer) is current and correct. The rest lags:
- Header still says *"Piece #1 … DONE … 64 tests pass"*, dated 2026-07-18, with two themes. There are now
  six-plus themes and a theme picker with live preview.
- §3's menu table is out of date: **File** omits Open Folder, Recent Projects, Compile; **View** omits
  Project Panel, Center Text, Formatting Preview, Theme; there is no **Tools** menu listed (Spellcheck,
  Spelling, Suggest, Autosave all live there) and no **Project** menu (all four StarBot commands);
  **Help** omits Welcome.
- §2's shortcut table omits Ctrl+X/C/V entirely.
- Closing line *"Nothing open — ready to implement"* is left over from before implementation.

**`docs/KEYMAP.md`** — a **superseded draft proposal**, still headed *"Prose — portable keymap (proposal
for sign-off)"* and *"Status: DRAFT — awaiting user approval. No bindings changed yet."* Its §4 proposes
F3 = Find Next, Shift+F3 = Find Previous, F4 = Replace All, `Ctrl+Shift+*` Tier-2 aliases throughout —
**none of which exist**; Replace All is Ctrl+L in the find bar. §8 lists six open decisions that were all
settled long ago in `MARKSTAR_KEYMAP.md`. Its §1 and §3 (terminal-encoding physics, reserved keys, stolen
F-keys) remain the best reference in the repo and are the only reason to keep the file. Recommend
retitling it to something like `TERMINAL_KEY_PHYSICS.md`, deleting §4/§5/§8, or marking it SUPERSEDED at
the top.

**`docs/PROSE_V0.1_DESIGN_SPEC.md`** — still called **Prose** throughout, product name and CLI binary
included (§1.1 *"CLI / binary: `prose`"*), and still names the AI assistant **ProseAI** (it is StarBot).
The repo field reads *"local workspace: `Documents/prose`"*. Beyond the rename:
- §5.9 promises a footer of *"Word count · L:C · dialect"* — **L:C was never built** (see the matrix).
- §5.4 says tab cycling is `Ctrl+Tab` / `Ctrl+Shift+Tab`; it is `Ctrl+PgUp` / `Ctrl+PgDn`.
- §5.5 says the project panel toggles on `Ctrl+Shift+E`; it is `Ctrl+P`.
- §5.6 says Replace All is `Ctrl+Shift+Enter` / `Ctrl+Shift+R`; it is `Ctrl+L` in the find bar.
- §6.1–6.3 are built almost entirely on `Ctrl+Shift+*` bindings (New in Project, Open Project Folder,
  Save As, Save All, Redo, Move Line, Duplicate Line, Next/Prev Tab) — the whole class of chord that
  `KEYMAP.md` later proved cannot be delivered by a terminal. §2.1 goal 3 still states the policy as
  *"predictable Ctrl / Ctrl+Shift bindings."*
- §3.4 lists *"Compile Project…"* with a flyout of targets; the shipped command is `File → Compile…` with
  no target picker.
- §12's roadmap still calls the assistant ProseAI and the config folder `.prose/config.toml`.

**`docs/HANDOFF.md`** — the most stale file in the repo, and dangerous to hand to a new agent:
- Titled *"Prose — session handoff"*, dated 2026-07-18, repo given as **`/home/daudzegir/Applications/prose`**
  and remote as `.../daudzegir/prose.git`. Both wrong; the tree is `MarkStarStudio` on branch `v0.3-file-ux`.
- Resume instructions tell the next agent to run `.venv/bin/prose` and expect **52 tests passing**; the
  entry point is `markstar`.
- Every source path is `src/prose/…`.
- Its entire stated purpose — *"Purpose of next session: Fix Replace All key delivery (blocking UX)"* —
  describes a bug that was solved by moving Replace All to `Ctrl+L`. The whole blocker section, the chord
  table, and the closing summary are now history, not instructions.
- Recommend either archiving it with a SUPERSEDED banner and a date, or replacing its contents with a
  current handoff.

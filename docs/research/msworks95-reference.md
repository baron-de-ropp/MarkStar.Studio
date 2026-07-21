# Microsoft Works 4.0 for Windows 95 — UX and Keyboard Reference

Research note for MarkStar Studio. Compiled 2026-07-21.

**Subject:** Microsoft Works for Windows 95, version **4.00.03.442**, © 1987–1995 Microsoft Corp.
(`MSWORKS.EXE`, PE32 GUI, 2,839,040 bytes, dated 1995-07-11.)

**Why this document exists:** MarkStar Studio is a Markdown-native WordStar homage, but its
*file lifecycle* and *keyboard conventions* should feel like a Windows-95-era CUA application
rather than WordStar's modal control-key world. Works 4.0 is the reference point: the friendly,
menu-driven, wizard-forward home application that shipped on millions of Windows 95 PCs.

---

## 0. Provenance and verification method

Almost everything in the keyboard and menu sections below is derived from **the shipped binary
itself**, not from secondary web sources. That is a deliberately higher standard of evidence:
a Win32 `RT_ACCELERATOR` resource is literally the table the application hands to
`TranslateAccelerator()`, so it is what the program actually did, not what a manual claimed
it did.

**Extraction chain**

1. Downloaded the CD image zip from the Internet Archive item
   [`microsoft-works-4.0-and-money-95-for-windows-95-4.0-1995-12-english-cd`](https://archive.org/details/microsoft-works-4.0-and-money-95-for-windows-95-4.0-1995-12-english-cd).
2. Extracted `MSCONTENT.iso`, then `/WORKS95/DISK1..DISK7/MSWORKS[1-7].CAB`
   (a spanning cabinet set — all seven must be co-located or `cabextract` fails mid-file).
3. Decompressed the cabinets, yielding `msworks.exe` and, critically, **`WKSLANG.DLL`** — the
   resource-only DLL holding every menu, accelerator table, and dialog in the product.
4. Parsed `RT_MENU` (type 4) and `RT_ACCELERATOR` (type 9) resources with `pefile`.
5. Mined readable strings from `wks4chid.hlp`, the context-sensitive help file, whose
   per-control descriptions survive uncompressed.

**Evidence files** (all under `docs/research/sources/extracted/`):

| File | What it is |
| --- | --- |
| `works4-accelerator-tables.txt` | All 21 decoded `RT_ACCELERATOR` tables |
| `works4-menu-resources.txt` | All 18 decoded `RT_MENU` resources, full menu trees |
| `works4-help-strings.txt` | 2,047 unique strings from `wks4chid.hlp` |
| `wkslang-strings-utf16.txt` | 399 unique UTF-16 strings from `WKSLANG.DLL` |
| `works4-version-info.txt` | PE version block proving 4.00.03.442 |
| `iso-listing.txt` | Full 2,161-entry ISO 9660 file listing |
| `parse-accelerators.py`, `parse-menus.py` | The parsers, for reproducibility |

**Tagging convention used throughout:**

- **[binary]** — read directly out of `WKSLANG.DLL`. Highest confidence.
- **[manual]** — stated in the printed Microsoft manual scan.
- **[help]** — from the shipped `wks4chid.hlp` strings.
- **[inferred]** — the *key binding* is proven present in the binary, but the *command it
  invokes* is identified only by convention (Word 6.0 / CUA), because Works stores its command
  labels outside any standard `RT_STRING` table and the un-menued IDs cannot be resolved.
- **[unverified]** — could not confirm; stated as an open question.

### What could NOT be verified

Recorded honestly, because these gaps matter:

- **Command IDs 27–53 have no menu entries and no string table.** `WKSLANG.DLL` contains
  `MENU`, `DIALOG`, `ACCELERATOR`, `CURSOR`, `BITMAP`, `ICON`, `VERSION` — **and no
  `STRINGTABLE` at all**. Works kept its status-bar/command text in a proprietary store. So for
  bold, italic, underline, alignment, line spacing and indent, I can prove *the key is bound*
  and prove *which command ID it fires*, but the human-readable name of that command ID is
  inference, not fact. Everything in that range is tagged **[inferred]**.
- **The main Works help file is not on the CD in decompilable form.** `wks4chid.hlp` is the
  context-sensitive help (dialog-control descriptions). It contains no consolidated
  "keyboard shortcuts" topic. `helpdeco` is not available in this environment, and WinHelp
  topic bodies are LZ77-compressed, so narrative help text could not be recovered.
- **The full Works 4.0 *User's Guide* was never obtained.** See §8.
- **Ctrl+Enter for page break** appears in the File/Insert menu text but *not* in the
  accelerator table, so it is menu-verified only — presumably handled inside the edit control.

---

## 1. The Works Task Launcher

This is the model for MarkStar's splash/welcome screen, so it is documented in the most detail.

### 1.1 What it is

> "When you start Works, you'll see the Works Task Launcher, **a dialog box with three tabs**.
> Each tab provides a different approach to starting a document."
> — *Microsoft Works for Windows 95 and Microsoft Money*, p. 3 **[manual]**

Note the wording: it is **a dialog box**, not a document window. It sits in front of the
otherwise-empty Works application frame.

### 1.2 The three tabs

Verbatim from the manual, p. 3 **[manual]**:

- **TaskWizards tab** — "to create a document with Works' expert assistance."
- **Existing Documents tab** — "to work on a document you already created in Works or another program."
- **Works Tools tab** — "to open a blank Word Processor, Spreadsheet, Database, or Communications document."

### 1.3 Tab-by-tab layout

Control names below are the literal help-topic identifiers from `wks4chid.hlp` **[help]**, so
they are the actual shipped control names.

**TaskWizards tab**
- `Click the Task Wizard You Want To Begin` — list box, left side
- `Description` — box on the right that explains the selected wizard
- `List Categories In Different Order` — button, opening options:
  `Alphabetical Order`, `Document Type`, `List By Category`, most-recently-used
- `Show TaskWizards In List` / `Show Templates In List` — check boxes
- `OK` button to launch

Help text for the list box **[help]**:
> "Lists a wide range of documents designed to help you perform common tasks. Click the scroll
> arrows to move up or down in the list, click the kind of document you want, and then click the
> OK button. You can click the List Categories In Different Order button to rearrange the list."

Manual procedure, p. 4 **[manual]**:
> "1 In the Task Launcher, click the TaskWizard tab. 2 Click a TaskWizard on the left side of
> the screen, and read about the kind of document it creates on the right. 3 When you're ready
> to start the TaskWizard, click the OK button."

**Existing Documents tab** — *the direct model for MarkStar's recent-files list*
- `Click The Document That You Want To Open` — list box of recently used documents
- `Path` — a display showing the full path of the highlighted document
- **`Open A Document Not Listed Here`** — button (exact shipped string:
  `&Open a document not listed here` **[binary]**)
- `Help Me Find A Document` — button

The behavioural rule, from help **[help]**:
> "Click the scroll arrows to move up or down in the list, and then click the document you want.
> **If the document you want does not appear in the list, click the Open A Document Not Listed
> Here button.**"

And **[help]**: "The Existing Documents tab lists recently used documents that you can open in Works."

So: a bounded MRU list is the primary affordance, and the full file dialog is the explicit,
labelled escape hatch — not a peer option. That framing is the thing worth copying.

**Works Tools tab**
- Four large buttons: `WP`, `SS`, `DB`, `Com` **[help]**
- `OK` button and an `Exit Works` button **[help]**

Help text for the WP button **[help]**: "Click this to open a new Word Processor document."

### 1.4 Launch and re-entry behaviour

- **At startup** the Task Launcher appears automatically **[manual]**.
- **Which tab opens is a user preference.** Tools → Options → View tab offers radio buttons:
  `TaskWizard Tab`, `Existing Documents`, `Works Tools`, and "the Task Launcher tab that was
  last displayed in the previous session" **[help]**.
- **Via the menus:** File → New (`Ctrl+N`) re-opens the Task Launcher. The command's own
  description string is: *"Displays Task Launcher for access to documents, templates, and
  TaskWizards."* **[binary]** — i.e. New does not silently create a blank document, it returns
  you to the home screen.
- **Dismissing it with nothing open** triggers a confirmation, verbatim **[binary]**:
  > "Are you sure you want to close the Task Launcher?##There are no documents to open, so
  > closing the Task Launcher will leave a blank workspace. **You can click anywhere in the
  > blank area to display the Task Launcher again.**"

  (`##` is Works' message/explanation separator.) The empty workspace is itself a hit target
  that summons the launcher back. There is no way to get stranded.
- A `Confirm TaskWizards` option controls whether choosing a wizard shows a confirmation
  dialog first **[help]**.

**Design lesson for MarkStar:** the launcher is *modal but never trapping*, it *remembers which
tab you used*, it puts **recent documents** ahead of the file browser, and it labels the browser
escape hatch in a full sentence rather than an icon.

---

## 2. Word processor keyboard shortcuts

Source of truth: `RT_ACCELERATOR` table **117** (the word-processor table, 384 bytes) plus frame
table **116**, cross-referenced against `RT_MENU` resource **10** (the word-processor menu bar).
Command IDs are given so the mapping is auditable against
`sources/extracted/works4-accelerator-tables.txt`.

### 2.1 Verified — accelerator and command both confirmed

These appear in the accelerator table *and* carry the same command ID as a labelled menu item,
so both the key and its meaning are proven. **[binary]**

| Key | Command | ID |
| --- | --- | --- |
| `Ctrl+N` | File → New… (opens Task Launcher) | 54 |
| `Ctrl+O` | File → Open… | 55 |
| `Ctrl+W` | File → **Close** | 57 |
| `Ctrl+S` | File → Save | 58 |
| `Ctrl+P` | File → Print… | 64 / 5 |
| `Ctrl+Z` | Edit → Undo | 69 |
| `Alt+Backspace` | Edit → Undo (alternate) | 69 |
| `Ctrl+X` | Edit → Cut | 70 |
| `Shift+Delete` | Edit → Cut (alternate) | 70 |
| `Ctrl+C` | Edit → Copy | 71 |
| `Ctrl+Insert` | Edit → Copy (alternate) | 71 |
| `Ctrl+V` | Edit → Paste | 72 |
| `Shift+Insert` | Edit → Paste (alternate) | 72 |
| `Ctrl+A` | Edit → Select All | 75 |
| `Ctrl+G` | Edit → Go To… | 76 |
| `F5` | Edit → Go To… (alternate) | 76 |
| `Ctrl+F` | Edit → **Find…** | 77 |
| `Ctrl+H` | Edit → **Replace…** | 78 |
| `F7` | Tools → Spelling… | 111 |
| `Shift+F7` | Tools → Thesaurus… | 112 |
| `F9` | Tools → Paginate Now | 116 |
| `F1` | Help | 7 |
| `Ctrl+Enter` | Insert → Page Break *(menu text only, not in accel table)* | 91 |

**Answering the brief's open question directly: Find is `Ctrl+F`, Replace is `Ctrl+H`, and
`Ctrl+G` is Go To.** Not `Ctrl+G` for find. This matches Word, not WordStar.

**Note the deliberate CUA double-binding.** Works shipped *both* generations of clipboard keys:
the Windows 3.x/CUA-classic `Shift+Delete` / `Ctrl+Insert` / `Shift+Insert` set and the modern
`Ctrl+X` / `Ctrl+C` / `Ctrl+V` set, on identical command IDs. That is a concrete example of the
era's "meet the user wherever they came from" philosophy.

### 2.2 Verified binding, inferred command

The key is definitively bound in table 117; the command ID has no menu entry, so its name is
read off Word 6.0 / Windows CUA convention. **[binary]** for the binding, **[inferred]** for the label.

| Key | ID | Almost certainly | Confidence |
| --- | --- | --- | --- |
| `Ctrl+B` | 28 | Bold | High — Windows CUA standard lists `CTRL+B: Bold` |
| `Ctrl+U` | 29 | Underline | High — CUA lists `CTRL+U: Underline` |
| `Ctrl+I` | 30 | Italic | High — CUA lists `CTRL+I: Italic` |
| `Ctrl+L` | 35 | Align left | Medium-high (Word convention) |
| `Ctrl+E` | 36 | Align centre | Medium-high (Word convention) |
| `Ctrl+Shift+R` | 37 | Align right | Medium — **note it is not plain `Ctrl+R`** |
| `Ctrl+J` | 38 | Justify | Medium-high (Word convention) |
| `Ctrl+1` | 39 | Single line spacing | Medium (Word convention) |
| `Ctrl+2` | 40 | Double line spacing | Medium (Word convention) |
| `Ctrl+5` | 41 | 1.5 line spacing | Medium (Word convention) |
| `Ctrl+0` | 42 | Space-before paragraph toggle | Medium (Word convention) |
| `Ctrl+M` | 46 | Increase indent | Medium (Word convention) |
| `Ctrl+Shift+M` | 45 | Decrease indent | Medium (Word convention) |
| `Ctrl+Q` | 34 | Remove paragraph formatting | Medium (Word convention) |
| `Ctrl+Space` | 27 | Remove character formatting | Medium (Word convention) |
| `F8` | 53 | Extend selection | Medium (Word convention) |
| `Shift+F8` | 52 | Shrink selection | Medium (Word convention) |
| `Shift+F5` | 48 | Return to previous edit point | Medium (Word convention) |
| `F6` / `Shift+F6` | 49 | Switch split pane — **both map to ID 49** | Medium; Works' only split is 2-pane, so direction is moot |
| `Shift+F4` | 50 | Repeat find | Medium (Word convention) |
| `Ctrl+Y` | 51 | **Repeat last action, not Redo** | Medium-high — the Edit menu has Undo and *no* Redo item at all |
| `Ctrl+Shift+F` | 3 | Focus font-name box on toolbar | Medium (Word convention) |
| `Ctrl+Shift+P` | 4 | Focus font-size box on toolbar | Medium (Word convention) |

Two findings here are load-bearing for MarkStar and worth stating plainly:

1. **Right-align is `Ctrl+Shift+R`, not `Ctrl+R`.** Plain `Ctrl+R` is *entirely unbound* in the
   word processor. (In the spreadsheet, `Ctrl+R` is Fill Right — see §2.4.) So Works itself broke
   the Word alignment quartet.
2. **Works had no Redo.** The Edit menu contains `&Undo \t Ctrl+Z` and nothing else in that
   group. `Ctrl+Y` is the Word-6 "Repeat" verb, not redo. Single-level undo was the norm.

### 2.3 Verified absences

Genuine negatives, confirmed by exhaustive search of all 21 accelerator tables and 18 menus:

- **No `F12` for Save As.** `Save &As...` (ID 59) has **no accelerator at all** — no F12, no
  `Ctrl+Shift+S`. It was menu-only. This is a real difference from Word.
- **No `Ctrl+F4`, `Ctrl+F6`, `Ctrl+Shift+F6`, or `Alt+F4` in Works' own tables.** They were not
  absent from the product — they came free from Windows. `msworks.exe` imports
  **`TranslateMDISysAccel`**, `DefMDIChildProcA` and registers `MDICLIENT` **[binary]**, which is
  exactly the mechanism that gives an MDI app `Ctrl+F4` (close child), `Ctrl+F6`/`Ctrl+Tab`
  (cycle children) and `Alt+F4` (quit) without the app declaring them. So those keys **did** work
  in Works, supplied by the OS.
- **`Ctrl+W` is Works' own close accelerator** (ID 57), declared explicitly — sitting alongside
  the OS-provided `Ctrl+F4`. Works chose the friendlier key and let the CUA-standard one keep working.

### 2.4 Other tools, for contrast

Works was one program with four tools; each swapped in its own accelerator table.
Same keys, different meanings **[binary]**:

| Key | Word processor | Spreadsheet | Database |
| --- | --- | --- | --- |
| `Ctrl+R` | *unbound* | Fill Right (167) | — |
| `Ctrl+D` | *unbound* | Fill Down (168) | — |
| `F9` | Paginate Now (116) | Recalculate Now (202) | Form view (312) |
| `Ctrl+F9` | — | — | Form Design (711) |
| `Shift+F9` | — | — | List view (313) |
| `Ctrl+Shift+X` / `Ctrl+Shift+C` | — | — | Cut / Copy **Record** |

The database also used `Ctrl+Shift+Plus` to insert and `Ctrl+Minus` to delete records and
fields **[help]**.

---

## 3. File lifecycle UX

### 3.1 Opening

File → Open… (`Ctrl+O`) presents the **Windows 95 common file dialog**. Confirmed by the help
topic name `Open/Save command: Drive/Look In/Save In dropdown list box` **[help]** — "Look In"
and "Save In" are the Win95 common-dialog labels (Windows 3.1 used "Drives"/"Directories", and
the topic covers both because the same help shipped across versions).

Two entry points to opening a document, by design: the Task Launcher's Existing Documents tab
(recent list first), or the full dialog via File → Open or the launcher's
"Open a document not listed here" button.

### 3.2 Saving

Save-on-untitled behaves exactly as modern apps do. Verbatim from the manual, p. 6 **[manual]**:

> **To save a document**
> Click the File menu, and then click Save.
> **If this is the first time you've saved the document, Works displays the Save As dialog box
> so you can name, and then save the document.**

So `Ctrl+S` on a never-saved document promotes itself to Save As. No separate "name this first"
step, no modal nag.

**Save As options** (help-topic names, so these are real controls) **[help]**:
- `Save As command: Create Backup Copy` check box —
  > "Specifies that Works will make a second, backup copy when you save the document. The backup
  > copy will preserve the last version of the document; the current copy will always contain the
  > latest changes you make."
- `Save As command: Template` button, opening a template dialog with
  `Use this Template For New Docs` check box, `Default Template` display, `Clear` / `Clear All`
  / `Defaults` buttons.

**Backup is opt-in per-save, not a global autosave.** No timed autosave feature was found
anywhere in the resources or help strings. **[unverified]** whether any autosave existed —
I found no evidence of one, and the absence of any related string is fairly strong negative
evidence.

Read-only documents were handled by redirecting to Save As **[help]**:
> "Specifies that Works will prevent changes to the file while it is open. To save changes to a
> read-only document, use the Save As command and save the file with a new name."

### 3.3 Closing with unsaved changes

The exact shipped prompt template, pulled from `WKSLANG.DLL` **[binary]**:

```
Save changes to %1?
```

`%1` is the document name — so a never-saved word-processor document produced
**"Save changes to Word1?"**. (Works named untitled documents by tool: the WP used
`Word1`, `Word2`…, not Word's `Document1`. **[inferred]** from the tool-prefixed naming
convention visible in the product; the literal untitled-name string was not recovered, so treat
the exact token as **[unverified]**.)

The dialog is the standard CUA three-button **Yes / No / Cancel**. **[inferred]** — the button
set is not stored as a string (Windows supplies it via `MB_YESNOCANCEL`), but a save-prompt with
a Cancel path is required behaviour for the era and Works offers no alternative mechanism.

A richer related prompt, verbatim **[binary]**:
> "This document contains unsaved Link information. Save changes to %1?"

> "This document contains a link to the database %1, which is not saved.##If you continue, the
> link will be invalid when you use this document again. Do you want to save the database before
> continuing?"

Note the house style: **problem statement, `##`, then consequence and remedy.** Every Works error
string follows it. That is a good pattern for MarkStar's own dialogs — never a bare error,
always "here is what happens next".

### 3.4 Quitting

File → **Exit Works** (ID 67, no accelerator; `Alt+F4` via Windows). Note the label is
"Exit Works", not "Exit" — the application names itself in its own quit command **[binary]**.

### 3.5 Document windows (MDI)

Works is a **single application frame containing multiple document windows** — classic MDI,
proven by the `MDICLIENT` window class and `DefMDIChildProcA` / `TranslateMDISysAccel`
imports **[binary]**.

The Window menu is minimal — `Cascade`, `Tile`, `Arrange Icons`, `Split` **[binary]**. There is
no static window list in the resource, because Windows' MDI implementation *appends the open
document list to the Window menu automatically* at runtime, numbered `1`, `2`, `3`… with
`Alt+W`,`1` style access.

Crucially, **all four tools share one frame**: opening a spreadsheet from the Task Launcher
while a document is open swaps the menu bar and toolbar in place rather than launching a
separate application. The window class names confirm the model: `MSWorks4.Doc`,
`MSWorks4.Doc.Chart`, `MSWorks4.Doc.Communication` **[binary]**.

---

## 4. Menu structure (word processor)

Decoded verbatim from `RT_MENU` resource 10. `&` marks the Alt-accelerator letter; command IDs
in parentheses. **[binary]**

**&File** — `&New... Ctrl+N` (54) · `&Open... Ctrl+O` (55) · `&Close Ctrl+W` (57) · — ·
`&Save Ctrl+S` (58) · `Save &As...` (59) · — · `Pa&ge Setup...` (61) · `Print Pre&view` (63) ·
`&Print... Ctrl+P` (64) · — · `S&end...` (66) · — · `E&xit Works` (67)

**&Edit** — `&Undo Ctrl+Z` (69) · — · `Cu&t Ctrl+X` (70) · `&Copy Ctrl+C` (71) ·
`&Paste Ctrl+V` (72) · `Paste &Special...` (73) · `Cle&ar Del` (74) ·
`Select A&ll Ctrl+A` (75) · — · `&Find... Ctrl+F` (77) · `R&eplace... Ctrl+H` (78) ·
`&Go To... Ctrl+G` (76) · — · `Easy Te&xt...` (753) · `&Bookmark...` (95) · — ·
`Lin&ks...` (79) · `&Object` (80)

**&View** — `&Normal` (83) · `&Page Layout` (84) · — · `&Toolbar` (81) · `&Ruler` (88) · — ·
`&All Characters` (87) · — · `&Header` (90) · `&Footer` (518) · `F&ootnotes` (89) · — ·
`&Zoom...` (82)

**&Insert** — `Page &Break Ctrl+Enter` (91) · `&Page Number` (123) · `Doc&ument Name` (127) ·
`&Date and Time...` (242) · `&Special Character...` (92) · `Database &Field...` (94) · — ·
`Easy Te&xt` (785) · — · `Foot&note...` (93) · — · `&Table...` (740) · `&Chart...` (96) ·
`Sp&readsheet...` (97) · `Clip&Art...` (98) · `&WordArt...` (99) · `Not&e-It...` (100) ·
`Draw&ing...` (101) · `&Object...` (103)

**F&ormat** — `&Font and Style...` (104) · `&Paragraph...` (105) · `&Tabs...` (106) ·
`&Borders and Shading...` (107) · `Bu&llets...` (85) · `&Columns...` (108) · — ·
`&Easy Formats...` (672) · — · `Text &Wrap...` (799) · `Pictu&re...` (109)

**&Tools** — `&Address Book...` (775) · `&Dial This Number` (110) · — ·
`&Spelling... F7` (111) · `&Thesaurus... Shift+F7` (112) · `&Hyphenation...` (113) ·
`&Word Count` (114) · `Look&up Reference...` (637) · — · `&Envelopes...` (115) ·
`&Labels...` (622) · `&Form Letters...` (640) · — · `Paginate &Now F9` (116) · — ·
`&Customize Toolbar...` (117) · `&Options...` (118)

**&Window** — `&Cascade` (119) · `&Tile` (120) · `&Arrange Icons` (121) · `S&plit` (122)

**&Help** — `&Contents...` (23) · `&Index...` (21) · — · `I&ntroduction to Works...` (25) ·
`How to &use Help` (636) · `&Show/Hide Help` (751) · `&Office Compatible` (22) ·
`&Launch Works Forum` (790) · — · `&About Microsoft Works` (26)

**Observations worth stealing:**

- Only **eight** top-level menus, and **every** item is reachable by `Alt` + letter. Full
  keyboard operability without a single memorised chord.
- The Format menu is only ten items. Formatting depth lives in dialogs, not in menu sprawl.
- `Show/Hide Help` in the Help menu reflects the docked help pane (see §5).
- The right-click context menu for body text (`RT_MENU` 907) is:
  Cut · Copy · Paste · Paste Special… · Clear · — · Font and Style… · Paragraph… ·
  Borders and Shading… · Bullets… **[binary]** — clipboard first, then the four format dialogs.

---

## 5. What makes the Works-95 feel distinct (vs WordStar)

The two programs solve the same problem with opposite theories of the user.

**WordStar is a language.** Its power lives in a memorised grammar of prefixed control chords —
`^K` opens the block/file menu, `^Q` the quick-movement menu, `^O` onscreen formatting, and the
meaning of the next keystroke depends entirely on which prefix preceded it. `^KS` saves,
`^KD` saves and exits, `^QF` finds. Modal, compositional, and once fluent, extremely fast. The
menus exist to teach you the chords and then get out of the way. The cost is a cliff: nothing is
guessable, and the same physical key means different things depending on state.

**Works is a surface.** Everything is visible, discoverable, and non-modal. Its theory:

1. **The Task Launcher as home base.** WordStar drops you at a no-file opening menu. Works
   opens a three-tab dialog that answers "what are you trying to do today?" — start a wizard,
   resume recent work, or open a blank tool. You cannot get lost, and dismissing the launcher
   with nothing open explains how to get it back.
2. **Wizards over documentation.** TaskWizards generate a formatted letter, résumé or newsletter
   from a short interview. WordStar's equivalent capability is a manual, a dot-command, and
   patience.
3. **Menu-driven with accelerators as an optional accelerant.** Every command has an `Alt`
   path and a menu home; `Ctrl+` keys are shown *on the menu item*, so the menu teaches the
   shortcut. Discovery precedes speed. WordStar inverts this.
4. **Non-modal, single-meaning keys.** `Ctrl+S` is always Save. In WordStar, `^S` is
   cursor-left, and Save is `^KS`. There is no Works keystroke whose meaning depends on a
   previous keystroke — the closest thing, `Ctrl+Shift+R`, is a simultaneous chord, not a
   sequence.
5. **The consequence-explaining dialog.** The `##` house style — statement, then what happens
   next and how to fix it — treats the user as someone who deserves an explanation rather than
   an error code.
6. **A docked help pane, not a modal help window.** "Works displays the Help window **next to**
   your document as you work" (manual p. 5) **[manual]**, toggled by Help → Show/Hide Help.
   Assistance is ambient, not an interruption.
7. **Bilingual shortcuts.** Shipping both `Ctrl+Insert` and `Ctrl+C` for Copy is the whole
   philosophy in miniature: never make the user unlearn something to use your program.

MarkStar wants WordStar's *aesthetic and density* with Works' *social contract*: nothing hidden
behind a memorised sequence, every command visible somewhere, and the welcome screen doing the
work of orienting you.

---

## 6. Recommended bindings for MarkStar (terminal-safe subset)

### 6.1 The hard constraint terminals impose

This is the single most important section, because a large fraction of the Works/CUA set is
**physically unrepresentable in a terminal**, regardless of design preference.

A terminal delivers `Ctrl+<letter>` as a single control byte (`Ctrl+A` = 0x01 … `Ctrl+Z` = 0x1A).
Several of those bytes are already the encoding of an ordinary key, so the application
**cannot distinguish them**:

| Combination | Byte | Indistinguishable from | Verdict |
| --- | --- | --- | --- |
| `Ctrl+I` | 0x09 | **Tab** | Unusable |
| `Ctrl+H` | 0x08 | **Backspace** | Unusable |
| `Ctrl+M` | 0x0D | **Enter** (CR) | Unusable |
| `Ctrl+J` | 0x0A | **Line feed** | Unusable |
| `Ctrl+[` | 0x1B | **Esc** | Unusable |

Further, `Ctrl+Shift+<letter>` produces **the same byte** as `Ctrl+<letter>` — a terminal has no
way to report the Shift. And `Ctrl+<digit>` is not a control byte at all for most digits; the
terminal simply sends the digit.

**Consequences for the Works set:**

- **`Ctrl+I` cannot be italic.** This *vindicates MarkStar's existing `Ctrl+E` for italic* —
  the CUA-authentic key is impossible, so a substitute is mandatory, and `Ctrl+E` is a
  reasonable one. **Recommendation: keep `Ctrl+E` = italic.** (It costs us Works' centre-align,
  which is unavoidable.)
- **`Ctrl+H` cannot be replace.** This *vindicates MarkStar's existing `Ctrl+R`* — and pleasingly,
  Works left plain `Ctrl+R` unbound in the word processor, so there is no authenticity conflict
  at all. **Recommendation: keep `Ctrl+R` = replace.**
- **All alignment shortcuts are lost.** `Ctrl+L` survives, but `Ctrl+E` is spent on italic,
  `Ctrl+Shift+R` is unrepresentable, `Ctrl+J` is line feed. A partial quartet is worse than none.
  **Recommendation: put alignment on the F9 menu only.** (Markdown barely has alignment anyway.)
- **All line-spacing shortcuts are lost** (`Ctrl+1/2/5/0` are not control bytes). Not meaningful
  in Markdown regardless. **Drop.**
- **Indent shortcuts are lost** (`Ctrl+M` = Enter, `Ctrl+Shift+M` unrepresentable). Since
  indent/outdent matters for Markdown lists, **recommend `Tab` / `Shift+Tab` in list context**,
  which is the modern editor convention and needs no Ctrl key.
- **`Ctrl+Enter` (page break) is unrepresentable** — terminals send plain CR. Irrelevant for
  Markdown; drop.

### 6.2 Signal and flow-control hazards in MarkStar's current set

These keys *are* representable but are intercepted by the tty line discipline unless the app
puts the terminal in raw mode:

| Key | Hazard | Action needed |
| --- | --- | --- |
| `Ctrl+S` (save) | **XOFF** — freezes terminal output | Must ensure `IXON` is off |
| `Ctrl+Q` (quit) | **XON** — resumes output | Must ensure `IXON` is off |
| `Ctrl+C` | `SIGINT` | Must ensure `ISIG` off (or handle) |
| `Ctrl+Z` (undo) | `SIGTSTP` — suspends the app | Must ensure `ISIG` off |
| `Ctrl+\` | `SIGQUIT` + core dump | Leave unbound |

Any competent TUI layer sets raw mode and neutralises all of these, so **`Ctrl+S`, `Ctrl+Q` and
`Ctrl+Z` are all safe to keep** — but this must be a deliberate, tested guarantee rather than an
assumption, because the failure mode (`Ctrl+S` freezing the user's terminal with no visible
cause) is severe and confusing. **Recommend an explicit startup assertion that `IXON` and `ISIG`
are cleared.**

### 6.3 Conflict table against MarkStar's current bindings

| Key | Works 4.0 | MarkStar now | Verdict |
| --- | --- | --- | --- |
| `Ctrl+N` | New (Task Launcher) | New | **Match.** Consider making it open the welcome screen, as Works did |
| `Ctrl+O` | Open | Open | **Match** |
| `Ctrl+S` | Save | Save | **Match** (watch XOFF) |
| `Ctrl+W` | Close | Close | **Match** — and Works chose `Ctrl+W` over `Ctrl+F4` too |
| `Ctrl+A` | Select All | Select All | **Match** |
| `Ctrl+F` | Find | Find | **Match** |
| `Ctrl+B` | Bold | Bold | **Match** |
| `Ctrl+Z` | Undo | *(undo)* | **Match** (watch SIGTSTP) |
| `Ctrl+X`/`C`/`V` | Cut/Copy/Paste | — | **Adopt as-is** |
| `F7` | Spelling | Spellcheck | **Match** |
| `Ctrl+E` | Centre align | **Italic** | **Keep MarkStar's.** Works' key is impossible (`Ctrl+I` = Tab) |
| `Ctrl+R` | *unbound in WP* | **Replace** | **Keep MarkStar's.** No conflict; Works' `Ctrl+H` = Backspace |
| `Ctrl+G` | **Go To** | **Spell-suggest** | **Conflict — see below** |
| `Ctrl+P` | **Print** | **Project panel** (fixed by Baron) | **Print must move — see below** |
| `Ctrl+Y` | Repeat | **Redo** | Divergent but fine — Works had no redo at all |
| `Ctrl+Q` | Clear para format | **Quit** | Fine; Works' meaning is unrepresentable anyway |
| `Ctrl+K` | — | StarBot | No conflict |
| `F9` | Paginate Now | **Menu** | Fine — pagination is meaningless in Markdown |
| `Ctrl+PgUp/PgDn` | *(MDI: `Ctrl+F6`)* | Tab cycling | **Risky — see below** |

### 6.4 Specific proposals

**1. Print / Export → `F5`.** `Ctrl+P` stays the project panel per Baron's decision, so the
Works binding is the side that moves. `F5` is free in MarkStar, is a single key (no chord),
is reliably delivered by every terminal, and Works' own use of `F5` (Go To) is already
duplicated on `Ctrl+G`. Put "Export / Print…" in the File menu under `F9` as the discoverable
home, with `F5` as the accelerator shown on the menu item — exactly Works' teaching pattern.

**2. Save As → `F12`.** Works left Save As with **no accelerator at all**, which was a genuine
gap. `F12` is free, terminal-safe, single-key, and matches the Word convention users of the era
actually had in their fingers. This improves on Works rather than copying its omission.

**3. Resolve `Ctrl+G`.** Works' Go To is a real word-processor verb and `Ctrl+G` is its
CUA-correct home; MarkStar currently spends it on spell-suggest. Two options, in preference order:
   - **Preferred:** move spell-suggest to **`F8`** (adjacent to `F7` spellcheck, mnemonically
     paired, single key, free) and give `Ctrl+G` back to **Go To Line**. This is both more
     Works-authentic and a better mnemonic grouping.
   - Alternative: keep `Ctrl+G` as spell-suggest and put Go To Line on **`Ctrl+L`** — which is
     free in MarkStar, is the common terminal-editor convention for "go to line", and whose
     Works meaning (align left) we have already conceded to the menu.

**4. Document cycling — add F-key fallbacks.** `Ctrl+PgUp` / `Ctrl+PgDn` are inconsistently
encoded across terminal emulators (many send the same sequence as plain PgUp/PgDn, some send
nothing). Keep them as the primary binding, but **add `F3` = next document and `Shift+F3` =
previous document** as guaranteed-deliverable equivalents. Works' own answer here (`Ctrl+F6`)
came from Windows MDI and has no terminal equivalent.

**5. Adopt Works' `Ctrl+N` semantics.** In Works, `Ctrl+N` did not create a blank document —
it reopened the Task Launcher ("Displays Task Launcher for access to documents, templates, and
TaskWizards"). If MarkStar's welcome screen is to be a genuine home base, `Ctrl+N` should
return to it rather than silently spawning `Untitled-2`.

**6. Adopt the `##` dialog style.** Statement, then consequence, then remedy. Cheap to do,
and it is the single most characteristic texture of the Works experience.

### 6.5 Recommended final set

Additions and changes only; unlisted current bindings stand.

| Key | Command | Rationale |
| --- | --- | --- |
| `F5` | Export / Print | `Ctrl+P` reserved for project panel |
| `F12` | Save As | Fills the gap Works left empty |
| `F8` | Spell-suggest *(moved)* | Pairs with `F7`; frees `Ctrl+G` |
| `Ctrl+G` | Go To Line *(restored)* | CUA-correct, Works-authentic |
| `F3` / `Shift+F3` | Next / previous document | Terminal-safe alternative to `Ctrl+PgUp/PgDn` |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / Copy / Paste | CUA core, if not already bound |
| `Tab` / `Shift+Tab` | Indent / outdent list item | `Ctrl+M` is Enter; this is the modern convention |
| *(menu only)* | Alignment, line spacing | Unrepresentable as terminal chords |

---

## 7. Downloaded and deleted artefacts

**Kept** in `docs/research/sources/`:

- `works4_installation_manual.pdf` (12,991,732 B) — Microsoft, *Microsoft Works for Windows 95
  and Microsoft Money*, Part No. 000-35721, © 1987–1996. 8 pages, 600 dpi scan, **no text layer**
  (no OCR tool available in this environment; pages were read visually).
- `winworld-works-40.html`, `wikipedia-microsoft-works.html`,
  `win95-keyboard-shortcuts-kb126449.html` — web captures.
- `extracted/` — all binary-derived evidence (see §0).

**Deleted after extraction**, per budget instruction:

| File | Size | Re-fetch from |
| --- | --- | --- |
| `works4_cd.zip` | 355,108,917 B | `https://archive.org/download/microsoft-works-4.0-and-money-95-for-windows-95-4.0-1995-12-english-cd/Microsoft%20Works%204.0%20and%20Money%2095%20for%20Windows%2095%20%284.0%29%20%281995-12%29%20%5BEnglish%5D%20%28CD%29.zip` |
| `MSCONTENT.iso` | 621,627,392 B | Inside the zip above, at `.../ISO/MSCONTENT.iso` |
| `works40_oem.iso` | 60,311,552 B | `https://archive.org/download/Microsoft_Works_4.0_CD/MMWORKS300.iso` — **do not bother; mislabelled** |

**To reproduce the binary evidence:** download the zip, `7z x` it, extract `MSCONTENT.iso`, copy
all seven `MSWORKS[1-7].CAB` from `/WORKS95/DISK1..7` **into a single directory** (the spanning
set fails otherwise), `cabextract MSWORKS1.CAB`, then run `extracted/parse-accelerators.py` and
`extracted/parse-menus.py` against `WKSLANG.DLL`.

**A warning for future researchers.** The Internet Archive item titled
["Microsoft Works 4.0 (OEM)"](https://archive.org/details/Microsoft_Works_4.0_CD) is **not Works
4.0**. Its `MMWORKS300.iso` has volume id `MMWORKS300`, contains `MSWORKS3.INF`, and its
`SETUP.INI` carries `OEM-MMWRKS300` — it is **Multimedia Works 3.0** for Windows 3.1. It was
downloaded, identified as wrong, and deleted. Use the Works 4.0 + Money 95 item instead.

---

## 8. Sources

**Primary — the shipped product**

- Microsoft Works for Windows 95 v4.00.03.442, `MSWORKS.EXE` / `WKSLANG.DLL` / `wks4chid.hlp`,
  extracted from
  <https://archive.org/details/microsoft-works-4.0-and-money-95-for-windows-95-4.0-1995-12-english-cd>
- Microsoft, *Microsoft Works for Windows 95 and Microsoft Money*, Part No. 000-35721,
  © 1987–1996 — `sources/works4_installation_manual.pdf`, from the same item.

**Secondary**

- Microsoft KB, "Keyboard shortcuts for Windows" (KB126449), archived —
  <https://web.archive.org/web/2016/https://support.microsoft.com/en-us/kb/126449>
  (the Windows CUA baseline: `CTRL+B` Bold, `CTRL+U` Underline, `CTRL+I` Italic, `ALT+F4` quit)
- WinWorld, Microsoft Works 4.0 — <https://winworldpc.com/product/microsoft-works/40>
- Wikipedia, Microsoft Works — <https://en.wikipedia.org/wiki/Microsoft_Works>

**Consulted but unobtainable — all borrow-only on the Internet Archive**

Each is `access-restricted-item: true` in the `inlibrary` / `printdisabled` collections; direct
PDF download returns HTTP 403 and the full-text search API returns "Item not available" without
a loan token. **No full Works 4.0 *User's Guide* PDF is openly available anywhere I could find.**

- Salkind, Neil J., *Running Microsoft Works for Windows 95* (Microsoft Press) —
  <https://archive.org/details/runningmicrosoft0000salk>
- *Field Guide to Microsoft Works for Windows 95* —
  <https://archive.org/details/fieldguidetomicr0000unse>
- *The Complete Idiot's Guide to Microsoft Works for Windows 95* —
  <https://archive.org/details/completeidiotsgu00pivo_1>
- *Microsoft Works for Windows 95: The Visual Learning Guide* —
  <https://archive.org/details/microsoftworksfo0000beat>

Anyone with an Internet Archive account can borrow these to close the **[inferred]** gaps in
§2.2 — specifically the identity of command IDs 27–53.

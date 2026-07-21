# WordStar Reference

A feature and command reference for WordStar, compiled for **MarkStar Studio** feature-parity work.

Every claim below is cited to a page in one of the primary sources in `sources/`. Nothing here is
from memory or from secondary web summaries except where explicitly marked `[Sawyer]`.

---

## Sources and citation convention

| Tag | Document | File |
|---|---|---|
| `WS4` | *WordStar Professional Release 4*, MicroPro International, 1987. 399 pages: Training Guide (printed pp. 1–113), Reference Guide (printed pp. 115–260), appendices. | `sources/Wordstar_Professional_Release_4.0_1987.pdf` |
| `WS3` | *WordStar Reference Manual*, WS-3SS0-1 (3.0), MicroPro International, first issue 15 May 1981. 156 pages, CP/M era. | `sources/Wordstar_3.0_Reference_Manual_May81.pdf` |
| `Sawyer` | Robert J. Sawyer, "WordStar: A Writer's Word Processor," 1990/1996. | `sources/sawyer-wordstar-essay-notes.md` (factual digest; original at sfwriter.com) |
| `jstarrc` | JOE's WordStar emulation keymap, from the locally installed `joe` package (`/etc/joe/jstarrc`). | `sources/jstarrc` |

Citations read `[WS4 p.161 (PDF 190)]`: **printed** page 161, which is **PDF** page 190 of the scan.
The two differ because of front matter, and the offset is not constant across the volume, so both
are given. WS3 uses section-relative numbering, cited as `[WS3 p.1-3 (PDF 19)]`.

**WordStar 4 is the canonical writer's version** and is the default source for everything below.
WordStar 3.0 is cited where the two releases differ, which matters more than expected — see §2.4.

**Notation.** `^K` means Ctrl-K. Two-character commands are prefix sequences: `^KB` is Ctrl-K then B
(the B may be typed with or without Ctrl held). Commands are case-insensitive
[WS4 TG p.20 (PDF 49)]. Dot commands are typed literally into the text starting in column 1.

---

## 1. The Opening Menu (the No-File menu)

This is the screen WordStar shows at startup before any file is open, and returns to whenever you
close a file. **It is the direct model for MarkStar's splash screen.**

### 1.1 WordStar 4, verbatim

Transcribed from the screen illustration at [WS4 TG p.20 (PDF 49)], confirmed against the Reference
Guide entry at [WS4 p.211 (PDF 238)]:

```
=============================== O P E N I N G   M E N U ===============================
   D open a document                  L change logged drive/directory
   N open a nondocument                C protect a file
   P print a file                      E rename a file
   M merge print a file                O copy a file
   I index a document                  Y delete a file
   T table of contents                 F turn directory off
   X exit WordStar                   Esc shorthand
   J help                              R run a DOS command

DIRECTORY    Drive B  336k free
  .1k CHAPTER1.DOC    .1k CHAPTER2.DOC    .1k CHAPTER3.DOC   3.5k DIARY.DOC
  .9k RULER.DOC       .6k SAMPLE1.DOC     .4k SAMPLE2.DOC     .3k SAMPLE3.DOC
  .9k TABLE.DOC      5.4k TEXT.DOC
```

### 1.2 Behavior

- **Single keystroke, no Enter.** "To choose a command at the Opening Menu, just type the command
  letter" [WS4 p.211 (PDF 238)]. Letters may be typed upper or lower case
  [WS4 TG p.20 (PDF 49)]. WS3 adds that the letter may also be typed with Ctrl held, and that
  unrecognized characters are simply ignored [WS3 p.1-3 (PDF 19)].
- **`^U` cancels** an Opening Menu command before the operation starts [WS4 p.211 (PDF 238)].
- **The directory display is live and part of the menu**, not a separate mode. It shows the drive,
  free space, and every file with its size. `F` toggles it off, and the menu line itself rewrites
  to read `turn directory on` when it is off [WS3 p.1-4 (PDF 20)].
- **You can open a file by pointing at it.** Rather than typing a name at the prompt, "move the
  cursor to the name of the file in the directory display, and press Enter"
  [WS4 TG p.48 (PDF 77)].
- **When the directory is too long to fit**, WordStar labels it `partial DIRECTORY` and you scroll
  it with `^Z` (up) and `^W` (down); a reminder line appears above the listing whenever scrolling
  would reveal more [WS3 p.1-7 (PDF 23)].
- **Help is a menu item.** Press `J`, then the letter of any command, to read what it does
  [WS4 TG p.20 (PDF 49)].
- **`?` reports memory use** — how much RAM WordStar and your files are consuming
  [WS4 p.186 (PDF 213)].
- Files with extensions `.COM`, `.EXE`, `.OVR`, and `.$?$` are hidden from the directory display
  [WS4 p.160 (PDF 189)].

### 1.3 The two file-open commands

`D` and `N` are the heart of the menu and the distinction is real, not cosmetic
[WS4 p.147 (PDF 176)]:

- **`D` open a document** — full word processing: word wrap, aligning, justification, margins,
  ruler line, centering, hyphen help, soft hyphens, line spacing. Dot commands are interpreted.
  The status line shows Page, Line, Column. WordStar uses the high bit of each byte for internal
  formatting information.
- **`N` open a nondocument** — plain ASCII, for data files and program source. No word wrap, no
  aligning, no ruler line, no Onscreen Format Menu. Status line shows only Line and Column. Tabs
  are real tab characters, set every 8 columns by default. `^QI` finds a *line* number rather than
  a page number. The high bit is left alone.

A file may be reopened in either mode; to convert a nondocument to a document you reopen it with
`D`, turn hard returns into soft ones with `^6`, and align the whole file with `^QU`
[WS4 p.147 (PDF 176)].

### 1.4 WordStar 3.0's No-File Menu, for comparison

[WS3 p.1-3 (PDF 19)]. The 1981 layout groups commands under printed headings:

```
                          <<< N O - F I L E   M E N U >>>
*** Preliminary Commands ***     |* File Commands *|* System Commands *
L Change logged disk drive       | P Print a file  | R Run a program
F File directory off (on)        | E Rename a file | X Exit to system
H Set help level                 | O Copy a file   |
*** Commands to Open a File ***  | Y Delete a file |* WordStar Options *
D Open a document file           | S Check spelling| M Run MailMerge
N Open a non-document file       |                 | S Run SpellStar
```

Differences worth noting for design purposes:

- WS3 puts **`H` set help level** directly on the no-file menu. WS4 folded this into `J` help
  [WS4 p.171 (PDF 198)].
- WS3 groups commands under explicit category headings (*Preliminary*, *Commands to Open a File*,
  *File*, *System*, *WordStar Options*). WS4 dropped the headings for a plain two-column list. The
  headed version is arguably the better splash-screen model — it teaches the shape of the program.
- The words `editing no file` are displayed while this menu is up [WS3 p.1-2 (PDF 18)].

---

## 2. File lifecycle commands

### 2.1 Saving, closing, abandoning

All from the Block & Save Menu; canonical descriptions at [WS4 p.235 (PDF 262)].

| Command | Semantics |
|---|---|
| `^KS` | **Save and resume.** Writes the file to disk, then **returns you to editing in the same place**. The manual explicitly recommends pressing it periodically as insurance against power failure [WS4 p.235 (PDF 262); p.157 (PDF 186)]. |
| `^KD` | **Save and done.** Writes the file, then returns to the **Opening Menu** — not to the operating system. This is the normal "close the document" command. |
| `^KX` | **Save and exit.** Writes the file, then exits WordStar to the operating system. |
| `^KQ` | **Quit without saving.** Abandons the editing session. The file on disk reverts to what it was when opened, *or* to the state of the last `^KS`. If changes exist, WordStar asks for confirmation. |
| `^PrtSc` | **Save and print.** Writes the file then prints it, offering the usual print options. Not available for merge printing. |
| `^KW` | **Write block to a separate file.** See §4. |

**The backup discipline:** when you open a document, the disk file stays put and you work on a copy
in memory. On save, the memory copy replaces the disk file and the previous disk file is retained
with a `.BAK` extension [WS4 p.235 (PDF 262)].

### 2.2 Operating on *other* files without leaving the one you are editing

This is one of WordStar's most distinctive traits and the manual gives it its own heading, "File
operations": *"Five commands on the Block & Save Menu let you manipulate other documents without
leaving the one you're currently editing"* [WS4 p.161 (PDF 190)].

| Command | Semantics |
|---|---|
| `^KJ` | **Erase a file.** Prompts for a filename. **Accepts wildcards** — `^KJ` then `*.BAK` erases every backup file [WS4 p.161 (PDF 190)]. |
| `^KL` | **Change the logged drive or directory**, so you can list and operate on files elsewhere. The directory display updates to the new location [WS4 p.161 (PDF 190); p.147 (PDF 176)]. |
| `^KO` | **Copy a file.** The original is preserved [WS4 p.161 (PDF 190)]. |
| `^KE` | **Rename a file** [WS4 p.161 (PDF 190)]. |
| `^KW` | **Write the marked block out to a separate file.** The block becomes a new file editable like any other; the original block stays in your working file [WS4 p.161 (PDF 190); p.123 (PDF 152)]. |
| `^KR` | **Read (insert) a file at the cursor.** Used for boilerplate, or to reassemble a document from parts. `^KR` can even insert a copy of the *current* file into itself — you get the version as of the last `^KS`, or as originally opened [WS4 p.123 (PDF 152)]. |
| `^KP` | **Print a file while editing** [WS4 p.222 (PDF 249, index)]. |

All of these except `^KL` prompt for a filename and display the disk directory while they do
[WS4 p.162 (PDF 191)]. `^KO` and `^KE` are also the way to bring up the directory display mid-edit
[WS4 p.147 (PDF 176)].

The manual's stated motivation is disk-space triage — you discover mid-document that the disk is
full, so you erase, copy, or offload blocks without losing your editing session
[WS4 p.161 (PDF 190)]. For a modern writer the value is different but larger: **file management is
part of the editor, not a separate application.**

### 2.3 Performance note worth stealing

*"Operations with two or more small blocks can be faster than with one large block... when moving a
block a distance of 25 pages, writing the block to a new file (`^KW`), then reading in the file at
the new location (`^KR`), may be faster than moving the block (`^KV`)"* [WS4 p.121 (PDF 150)].

This is the "block operations work on files" idea Sawyer praises: the clipboard is the filesystem.

### 2.4 `^KF` — a genuine version split, do not assert one binding

The task brief listed `^KF` as "directory listing toggle." That is **WordStar 3.x behavior, and it
is not a `^K` command there at all.** The facts:

- **WordStar 3.0:** the directory toggle is the **`F` command on the No-File menu**, described as
  "File Directory Toggle. Controls display of file directory... The first F command turns the
  directory display off, the second F turns the directory display on again"
  [WS3 p.1-4 (PDF 20)].
- **WordStar 4:** the Opening Menu still uses **`F` turn directory off**
  [WS4 p.211 (PDF 238)], but **`^KF` while editing means "run a DOS command"**
  [WS4 p.120 (PDF 149), Block & Save Menu: `F run a DOS command`; p.256 (PDF 283)].

So in WS4 the pairing is `R` at the Opening Menu / `^KF` while editing, both meaning *run a DOS
command* [WS4 p.256 (PDF 283)]. **MarkStar should treat the directory toggle and the shell escape
as two separate features and choose its own keys**, rather than inheriting an ambiguous `^KF`.

### 2.5 The Block & Save Menu

Pressing `^K` displays it, at help levels 2 and 3 only; typing the two keys quickly bypasses the
display entirely [WS4 p.120 (PDF 149)]:

```
================================ B L O C K   &   S A V E ================================
 SAVE                      BLOCK                    CURSOR
 S save & resume edit      B mark begin             0-9 set/hide marker
 D save document           K mark end
 X save & exit WordStar    C copy                   FILE
 Q quit without saving     V move                   O copy       E rename
                           Y delete                 J erase      P print
                           H turn display on        L logged drive/dir
                           W write to disk          R insert a document
                           M math                   F run a DOS command
                           N turn column mode on
                           I turn column replace on
```

---

## 3. Cursor motion and scrolling

### 3.1 The diamond

The four single-key motions form a diamond under the left hand [Sawyer; WS4 p.136 "Cursor diamond"]:

```
      ^E  up
^S left    ^D right
     ^X  down
```

Full table, from the master listing at [WS4 p.139 (PDF 168)]:

| Motion | Command | Alt key |
|---|---|---|
| Up one line | `^E` | ↑ |
| Down one line | `^X` | ↓ |
| Left one character | `^S` | ← |
| Right one character | `^D` | → |
| Left one word | `^A` | Ctrl-← |
| Right one word | `^F` | Ctrl-→ |
| To column 1 of current line | `^QS` | |
| To end of current line | `^QD` | |
| To col. 1 of first onscreen line | `^QE` | Home |
| To last onscreen line | `^QX` | End |
| Directly to beginning of file | `^QR` | Ctrl-Home |
| Directly to end of file | `^QC` | Ctrl-End |

Note the geometry: `^Q` + a diamond key means "same direction, but further" — `^QS` goes to the
start of the line, `^QR` to the start of the file. This scaling rule is the reason the command set
is learnable, and MarkStar should preserve it.

### 3.2 Scrolling

[WS4 p.236 (PDF 263)]

| Command | Effect |
|---|---|
| `^W` | Scroll up one line (text moves down) |
| `^Z` | Scroll down one line (text moves up) |
| `^R` | Scroll up one screenful (also PgUp) |
| `^C` | Scroll down one screenful (also PgDn) |
| `^QW` | Scroll **continuously** upward, line by line |
| `^QZ` | Scroll **continuously** downward, line by line |
| `^QQ^R` | Screen-by-screen to beginning of file [WS4 p.139 (PDF 168)] |
| `^QQ^C` | Screen-by-screen to end of file |

Two details worth copying:

- With `^W`, `^Z`, `^QW`, `^QZ` the **cursor stays put in the text** while the view moves, until the
  line it is on scrolls off; only then does it jump to the top or bottom line
  [WS4 p.236 (PDF 263)].
- During `^QW`/`^QZ` continuous scroll you **type a digit 0–9 to change speed**, 0 fastest, 9
  slowest [WS4 p.236 (PDF 263)]. This is a reading mode, not just a navigation command.
- Horizontal scrolling happens automatically past column 80; `^QS` returns to column 1 when the left
  margin has scrolled out of view [WS4 p.236 (PDF 263)].
- The cursor cannot enter unwritten screen space — moving down from the end of a long line lands at
  the end of the shorter line below, not in the void [WS4 p.138 (PDF 167)].

### 3.3 "Finding your place" — the position commands

The manual gives these their own Reference Guide heading, which tells you how central they were
[WS4 p.165–166 (PDF 194–195)]:

| Command | Semantics |
|---|---|
| `^Q0`–`^Q9` | Go to numbered place marker previously set with `^K0`–`^K9`. |
| `^QB` | Go to the beginning of the marked block. |
| `^QK` | Go to the end of the marked block. |
| `^QI` | Go to a **page number** (a *line* number in nondocuments). Prompts for the number. Searching forward it lands on line 1 of the page; backward, on the last line. |
| `^QG` | Go forward to the next occurrence of a **character** (prompts for it). |
| `^QH` | Go backward to the previous occurrence of a character. |
| `^QP` | **Go to where the cursor was before the last command.** Verbatim: *"Goes to where the cursor was located before the last command. You can use this only immediately after the command is executed"* [WS4 p.166 (PDF 195)]. |
| `^QV` | **Go to where the most recent find string was located, or where the last marked block was.** |

`^QP` is the single most-loved command in the set and is worth restating precisely: it is a
**one-step positional undo**, valid immediately after the command that moved you. Paired with `^KS`
(save and resume, which does not move the cursor at all) and `^QV` (return to the last find or
block), these three give WordStar its reputation for never losing your place. MarkStar should
consider generalizing `^QP` into a **position history ring** — which is exactly what jstar did, see
§8.

### 3.4 The Edit Menu

`^J` shows it; it is the root menu displayed while editing at help level 3
[WS4 TG p.93 (PDF 122)]:

```
=================================== E D I T   M E N U ===================================
 CURSOR          SCROLL         ERASE        OTHER                  MENUS
 ^E up           ^W up          ^G char      ^J help                ^O onscreen format
 ^X down         ^Z down        ^T word      ^I tab                 ^K block & save
 ^S left         ^R up screen   ^Y line      ^V turn insert off     ^P print controls
 ^D right        ^C down screen Del char     ^B align paragraph     ^Q quick functions
 ^A word left                   ^U unerase   ^N split the line      Esc shorthand
 ^F word right                               ^L find/replace again
```

### 3.5 Deletion

[WS4 p.145 (index), p.65]

| Command | Deletes |
|---|---|
| `^G` | Character at cursor |
| `^H` / Backspace | Character to the left |
| `^T` | Word to the right |
| `^Y` | Entire line |
| `^QY` | To end of line |
| `^Q Del` | To beginning of line |
| `^QT` | Forward to a specified character (prompts) |
| `^KY` | The marked block |

All of these except single-character deletes can be reversed with `^U` — see §7.2.

---

## 4. Blocks, columns, and place markers

### 4.1 Marking

[WS4 p.121–122 (PDF 150–151)]

- `^KB` marks the beginning, `^KK` marks the end. Markers show as `<B>` and `<K>`; when the block
  between them is highlighted the markers are hidden and `B` / `K` flags appear in the flag column
  instead.
- **Only one begin marker and one end marker exist at a time.** If the end marker precedes the
  begin marker, both display but no block is marked.
- **Marking is decoupled from acting.** You may mark, keep writing indefinitely, and act later —
  the point Sawyer singles out as WordStar's key advantage over WordPerfect [Sawyer].
- To move a marker, re-enter its command at the new position. To erase one, re-enter its command
  with the cursor immediately to its right.
- To include a trailing hard carriage return in the block, put the end marker at the start of the
  *next* line.
- **Block markers are deleted automatically when you leave the file** — they do not persist across
  sessions.

### 4.2 Block operations

[WS4 p.122–123 (PDF 151–152)]

| Command | Semantics |
|---|---|
| `^KC` | **Copy** the block to the cursor. |
| `^KV` | **Move** the block to the cursor. |
| `^KY` | **Delete** the block. The cursor need not be anywhere near it; afterwards the cursor sits where the block was. Restorable with `^U`. |
| `^KW` | **Write** the block to a new file on disk (prompts for name; warns before overwriting). The block stays in the working file. |
| `^KR` | **Read** a file in at the cursor. |
| `^KH` | **Hide** block markers and highlighting; press again to show. |
| `^KM` | **Block math** — total all the numbers in the block, even if it also contains words. Result shows at the top of the screen; `Esc =` then inserts it into the text, `Esc $` as a dollar amount [WS4 p.120 (PDF 149)]. |
| `^K'` | Convert the block to lowercase. |
| `^K"` | Convert the block to uppercase [WS4 p.126 (index)]. |

**`^KH` is also a safety interlock:** at help levels 2 and 3, WordStar *refuses* to move, copy,
erase, or write a block while the markers are hidden [WS4 p.123 (PDF 152)]. Hiding a block is how
you protect it.

### 4.3 Column blocks

Turned on with `^KN`; the word `Column` appears in the status line [WS4 p.129 (PDF 158)].

- In column mode, `^KB` and `^KK` mark the **top-left and bottom-right corners** of a rectangle
  rather than a text run.
- `^KI` toggles **column replace**; status line shows `ColRepl`. With it on, a moved/copied/inserted
  block *overwrites* text at the destination and leaves a blank "hole" at the source. With it off,
  the block *pushes* existing text aside and the source closes up [WS4 p.129 (PDF 158)].
- Dot commands are never part of a column block; a dot command inside the rectangle stays put when
  the block moves [WS4 p.129 (PDF 158)].
- `^KW` behaves identically for column blocks. `^KR` in column mode expects the incoming file to be
  a column and warns if line lengths vary [WS4 p.130 (PDF 159)].
- `^U` can restore text that a column-replace operation overwrote [WS4 p.131 (PDF 160)].

Intended use case is table surgery — swapping two columns of a table [WS4 p.129 (PDF 158)].

### 4.4 Place markers

[WS4 p.218 (PDF 245)]

- **Ten markers, 0 through 9.** Set one with `^K` followed by a digit; the digit appears highlighted
  in the text. Jump to it from anywhere with `^Q` followed by the digit.
- Setting a marker at a new location **moves** it — the old one disappears.
- Re-entering `^K`*n* with the cursor on marker *n* **removes** it.
- `^KH` hides marker display along with block highlighting. Setting a new marker while markers are
  hidden re-displays everything until `^KH` is pressed again.
- **Markers are session-only.** *"Place markers are in effect only as long as you are editing the
  file. They are not saved when you leave the file"* [WS4 p.218 (PDF 245)].

That last point is a design decision MarkStar should consciously revisit — persisting markers across
sessions is cheap now and directly serves long-manuscript work.

---

## 5. Find and replace

### 5.1 The three commands

[WS4 p.162 (PDF 191)]

| Command | Semantics |
|---|---|
| `^QF` | Find a string. Moves the cursor to the next occurrence and **returns you to normal editing**. |
| `^QA` | Find and replace. Prompts for the search string, the replacement, then options. |
| `^L` | **Repeat** — find, or find and replace, the next occurrence of the same string. |

Default `^QA` behavior is interactive: find the next occurrence, ask whether to replace, act, then
drop back into editing so you can keep working; `^L` resumes. With `G` or `R` it runs straight
through without pausing [WS4 p.162 (PDF 191)].

**`^U` stops a find or replace in progress** [WS4 p.162 (PDF 191)].

### 5.2 Strings

[WS4 p.162–163 (PDF 191–192)]

- Up to **65 characters**, may include spaces and control characters.
- `^P` is the literal prefix: `^P^B` searches for a bold print control; `^P^M^P^J` matches a hard
  carriage return.
- `?` is a wildcard character when the `?` option is on — `Su??` matches Suzy, Susy, Suzi.
- To **delete** a string, use `^QA` and press Enter at the `Replace with?` prompt.
- The manual warns that matching is exact, including stray spaces.

### 5.3 Option letters

Typed together in one string at the `Option(s)?` prompt, e.g. `gn` [WS4 TG p.51 (PDF 80)].
Definitive list at [WS4 p.163–164 (PDF 192–193)]:

| Option | Meaning |
|---|---|
| `W` | **Whole words only.** Without it, `can` matches inside *can't*, *canned*, *American*, *scandal*. |
| `U` | **Ignore case.** |
| `B` | **Search backward** from the cursor toward the top of the file. |
| `?` | Treat `?` in the search string as a **wildcard**. Without it, `?` matches a literal question mark. |
| *n* | A **number**: with `^QF`, find the *n*th occurrence; with `^QA`, replace that many occurrences. Not shown on the options prompt. |
| `G` | **Global** — go to the beginning of the file (or the end, if `B` is also set) before searching. With `^QA`, replace throughout the whole file. |
| `R` | **Rest of document** — like `G` but does not jump to the file boundary first. `^QA` only. |
| `N` | **No ask** — replace without confirming each occurrence. |
| `A` | **Align paragraphs after each replacement**, returning the cursor to the replacement point afterward. |

Notes: default options are configurable via WSCHANGE; **selecting any option suppresses all
defaults** unless re-selected; pressing Space then Enter at the prompt means "no options at all"
[WS4 p.165 (PDF 194)]. Pressing Esc at the find/replace prompts suppresses the options question
entirely [WS3 p.1-8 (PDF 24)].

### 5.4 Character-level find

`^QG` / `^QH` search forward/backward for a single **character** rather than a string, and `^QT`
deletes forward to a character [WS4 p.165 (PDF 194); p.145].

---

## 6. Formatting

### 6.1 Aligning (reflowing) paragraphs

[WS4 p.116 (PDF 145)]

- **`^B` aligns the paragraph** — WordStar's term for reflowing text to the current margins. Put the
  cursor on the first line to align and press `^B`. It stops at the next hard carriage return.
- **`^QU` aligns the rest of the document** — aligns a paragraph, pauses briefly at the hard return,
  continues to the end of the file. **`^U` stops it.**
- If a temporary indent (`^OG`) is active, the temporary indent column is used as the left margin.
- `.AW off` / `.AW on` bracket regions (tables, charts) that must never be reflowed.
- `^PO` inserts a **binding space**, so a phrase is treated as one unbreakable word during aligning.
- The word `Align` appears in the status line during normal editing.
- With hyphen help on (`^OH`), WordStar stops at each word straddling the right margin and offers to
  hyphenate; you may move the cursor within the word first, type `-` to hyphenate there, press `^B`
  to move the whole word down instead, or `^U` to turn hyphen help off for the rest of the paragraph
  [WS4 p.172 (PDF 199)]. Hyphens inserted this way are **soft** — they print only if they still fall
  at a line end after later reflows [WS4 p.343 (PDF 372)].

### 6.2 The Onscreen Format Menu (`^O`)

[WS4 p.210 (PDF 237); also TG p.35 (PDF 64)]

```
============================= O N S C R E E N   F O R M A T =============================
 MARGINS                  TYPING                        DISPLAY
 L set left               W turn word wrap off          D turn print controls off
 R set right              J turn right justify off      H turn hyphen help on
 X release                E enter soft hyphen           P turn preview on
 T turn ruler off         G temporary indent
 F ruler from text        S set line spacing            TABS
 O ruler to text          C center line                 I set tab stop
                                                        N clear tab stop
```

| Command | Semantics |
|---|---|
| `^OL` | Set the **left margin** (column number, or Esc for the cursor's column) [WS4 p.183 (PDF 210 area)]. |
| `^OR` | Set the **right margin**. Default document margins are column 1 and column 65 [WS4 TG p.35 (PDF 64)]. |
| `^OX` | **Release margins** — type past the right margin temporarily [WS4 TG p.38 (PDF 67)]. |
| `^OC` | **Center the current line** between the current margins. Leading and trailing spaces are ignored. Re-center after editing the line; `^T` at column 1 un-centers by re-aligning left [WS4 p.127 (PDF 156)]. |
| `^OG` | **Temporary indent** — moves the left margin one tab stop right; repeat to indent further. Lasts until Enter. `^B` aligns to it and then clears it [WS4 p.343 (PDF 372)]. |
| `^OS` | Set **line spacing**. |
| `^OJ` | Toggle **right justification** (on by default; off gives ragged right) [WS4 TG p.39–40 (PDF 68)]. |
| `^OW` | Toggle **word wrap**. With it off you can type to column 255 and must press Enter yourself; WordStar beeps when you pass the right margin [WS4 p.257 (PDF 284)]. |
| `^OH` | Toggle **hyphen help**. |
| `^OE` | Insert a **soft hyphen**, displayed as `=` when not at a line end [WS4 p.343 (PDF 372)]. |
| `^OI` / `^ON` | **Set / clear a tab stop.** Prefix with `#` when setting to make it a decimal tab. Document tabs default to every 5 columns [WS4 p.343 (PDF 372); p.148 (PDF 177)]. |
| `^OT` | Toggle **ruler line** display. |
| `^OF` | **Ruler from text** — adopt the format of the line the cursor is on as the ruler. |
| `^OO` | **Ruler to text** — write the current ruler into the document as an embedded `.RR` ruler line [WS4 p.233 (index)]. |
| `^OD` | Toggle display of **print control characters** [WS4 p.219 (PDF 246)]. |
| `^OP` | Toggle **preview**: hides both dot commands and print controls, and switches to the protected menus so the document cannot be modified while previewing [WS4 p.219 (PDF 246)]. |
| `^OB` | Toggle display of **soft spaces** [WS4 p.343 (PDF 372)]. |

The **ruler line** sits at the top of the editing area showing current margins and tab stops
[WS4 TG p.35 (PDF 64)]. `.RR` embeds a ruler mid-document so format changes travel with the text
[WS4 p.152 (PDF 181)].

### 6.3 The flag column

A one-character gutter down the right edge annotating every line [WS4 p.166 (PDF 195)]:

| Flag | Meaning |
|---|---|
| `<` | Line ends with a **hard** carriage return (blank = soft, produced by word wrap) |
| `P` | **Page break** — a new page begins below this line |
| `F` | Line ends with a form feed (`^PL`) |
| `^` | The file ends on or above this line |
| `+` | Text extends beyond the right edge of the screen |
| `.` | Dot command affecting **both** screen and printout |
| `:` | Dot command affecting **printout only** |
| `?` | Unrecognized dot command (line still will not print) [WS4 p.149 (PDF 178)] |

This is a genuinely good idea that modern editors dropped: a persistent per-line status gutter
distinguishing hard from soft line endings and flagging structural lines.

### 6.4 Dot commands

Typed into the text: a period in column 1, a two-letter code, optional argument, Enter. Case
insensitive. **The line stays in the file but does not print** [WS4 p.148 (PDF 177)]. Must begin in
column 1 and must not be placed inside a paragraph, or reflowing may absorb it
[WS4 p.148 (PDF 177)]. Erase one with `^Y` [WS4 TG p.38 (PDF 67)]. To print a document *with* its
dot commands visible, print it as a nondocument [WS4 p.148 (PDF 177)].

**Writer-relevant onscreen-formatting dot commands** [WS4 p.151–152 (PDF 180–181)]:

| Command | Arg | Function |
|---|---|---|
| `..` | text | **Comment line** — see §7.5 |
| `.IG` | text | Comment line (identical to `..`) |
| `.LM` | number | Left margin column |
| `.RM` | number | Right margin column |
| `.PM` | number | Paragraph margin (indent for first line) |
| `.LS` | number | Line spacing |
| `.LH` | number | Line height, 48ths of an inch |
| `.OJ` | on/off | Right justification |
| `.AW` | on/off | Word wrap **and aligning** on/off — the way to protect tables |
| `.PA` | — | Force a **page break** |
| `.CP` | number | **Conditional page break** — keep *n* lines together |
| `.PL` | number | Page length in lines |
| `.PN` | number | **Set the page number** for the current page |
| `.RR` | text | Embedded ruler line |

**Writer-relevant print-formatting dot commands** [WS4 p.149–150 (PDF 178–179)]:

| Command | Arg | Function |
|---|---|---|
| `.HE` / `.H1` | text | **Header**, first line |
| `.H2` `.H3` | text | Header, second and third lines |
| `.HM` | number | Header margin, in lines |
| `.FO` / `.F1` | text | **Footer**, first line |
| `.F2` `.F3` | text | Footer, second and third lines |
| `.FM` | number | Footer margin |
| `.MT` / `.MB` | number | Top / bottom margin, in lines |
| `.PO` | number | Page offset from left edge |
| `.OP` | — | **Omit page numbers** |
| `.PG` | — | Resume page numbering |
| `.PC` | number | Column in which to print the page number |
| `.FI` | filename | **Insert the named file at print time** — file chaining |
| `.UL` | on/off | Underline the spaces between words too |

`.FI` deserves note: it makes a book out of chapter files at print time, and a "command file" of
nothing but `.FI` lines prints a whole multi-file manuscript in order with **continuous page
numbering across files** [WS4 p.209 (PDF 236)]. That is the 1987 answer to a Markdown book build.

### 6.5 Print controls (`^P`)

Paired toggles embedded in the text; the opening and closing marks are the same command
[WS4 p.219 (PDF 246)]:

```
================================ P R I N T   C O N T R O L S ================================
 BEGIN & END                          OTHER
 B bold          X strike out         H overprint char    O binding space
 S underline     D double strike      ^J overprint line   C print pause
 T superscript   Y italics/color      F phantom space     I column tab
 V subscript     X indexing           G phantom rubout    @ fixed position
                                      Q W E R custom      N normal pitch
                                      L form feed         A alternate pitch
```

The writer-relevant ones: **`^PB` bold**, **`^PS` underline**, **`^PY` italics** (or second ribbon
colour), **`^PX` strikeout**, **`^PT` superscript**, **`^PV` subscript**, **`^PD` double strike**,
**`^PK` mark index entry**. Controls appear inline as `^B`, `^S` and so on, and the affected text is
highlighted; `^OD` hides the markers while keeping the highlighting [WS4 p.220 (PDF 247);
TG p.58 (PDF 87)].

Deleting one half of a pair silently extends the effect to the rest of the document — the manual
warns about it explicitly [WS4 TG p.58 (PDF 87)]. **MarkStar, being Markdown-native with paired
delimiters, should treat this as a solved problem and never let a user create an unbalanced pair.**

### 6.6 Index and table of contents

`I` and `T` on the Opening Menu generate an index and a table of contents from the document. Index
entries are marked either with the `^PK` print control around a phrase in the text, or with the
`.IX` dot command; exclusion lists and index-every-word modes exist
[WS4 p.174–176 (PDF 201–203)].

---

## 7. Other features writers loved

### 7.1 Help levels — progressive disclosure

[WS4 p.171 (PDF 198); set with `^J^J`, or `J` at the Opening Menu, or `H` on the WS3 No-File menu]

| Level | Behavior |
|---|---|
| **3** | All menus and prompts displayed. Default. |
| **2** | The Edit Menu is not displayed, but prompts are, and the other menus still appear if you pause after the prefix key. Full-screen document. |
| **1** | No menus during editing unless requested; certain prompts suppressed. |
| **0** | No menus, **no status line**, minimal prompts. |

Key properties:

- **Menus double as a timing-based disclosure mechanism.** At level 2, pressing `^K` and pausing
  shows the Block & Save Menu; typing `^KB` quickly executes without ever drawing it
  [WS4 p.120 (PDF 149)]. The menu is a hint that appears only when you hesitate. This is the single
  best idea in the WordStar interface and MarkStar should implement it exactly.
- `^J` shows the Edit Menu at any help level [WS4 p.171 (PDF 198)].
- Help is contextual: `^J` then a command letter explains that command; `^J?` explains the screen
  layout; `^J.` explains dot commands [WS4 p.172 (PDF 199)].
- The menus **take up a third of the screen**, which is the stated reason to turn them down
  [WS4 p.171 (PDF 198)].
- WS3 notes that typing the answer before the explanation renders skips the explanation entirely —
  *"provides rapid response for the user who knows what he wants"* [WS3 p.1-5 (PDF 21)].
- In a protected file, menus are redrawn **without** the commands that could modify the file
  [WS4 p.187 (PDF 214)].

### 7.2 `^U` — undo, unerase, and interrupt

[WS4 p.254 (PDF 281)]

One key does all of these:

- Cancel a response to a prompt before it is final.
- Stop `^QR` / `^QC` from running all the way to the top or bottom of the file.
- **Stop a find or find-and-replace.**
- Stop a spelling check.
- Stop hyphen help for the rest of a paragraph.
- **Stop printing.**
- **Restore text you just erased** ("unerase").

Unerase semantics [WS4 p.254–255 (PDF 281–282)]:

- Restores the **last group** of characters erased — one command's worth, so `^QY` yes, four
  consecutive `^T`s no.
- Text is reinserted **at the cursor**, not at the place it came from. The manual presents this as a
  feature: *"Unerasing is an easy way to move a short phrase. Erase the text, move the cursor, and
  press `^U`."*
- `^U` **does not empty the buffer**, so you can paste the same text repeatedly.
- Default buffer 500 characters. Single characters erased with `^G`, `^H`, Backspace or Del are not
  normally recoverable.
- If an erasure would exceed the buffer, WordStar warns and offers to cancel the command.

So `^U` is simultaneously the universal interrupt key and a one-slot kill ring. **MarkStar should
split these:** a real undo stack plus a separate interrupt key, while keeping the "erase, move,
unerase" move-by-cut idiom available.

### 7.3 Word count and document statistics

Two distinct facilities [WS4 p.255–256 (PDF 282–283)]:

- **`^Q?` while editing** displays the number of **characters from the beginning of the file to the
  cursor**. (This is a progress indicator, not a word count.)
- **A separate `WC` utility** ships with WordStar and reports **lines, words, and characters**, for
  one or many files at once, with totals — run it via `R` at the Opening Menu or `^KF` while
  editing. The manual's own example is a three-chapter book, totalling `chapter1.doc`,
  `chapter2.doc`, `chapter3.doc` to get overall manuscript length.

That example is exactly the MarkStar use case: **a word count that aggregates across a multi-file
manuscript.**

### 7.4 Spelling

[WS4 p.243 (index); TG p.51–53 (PDF 80–82)]

| Command | Semantics |
|---|---|
| `^QL` | Check spelling of the **rest of the document** from the cursor. |
| `^QN` | Check the spelling of the **word at the cursor**. |
| `^QO` | **Type a word** and check it without inserting it — a spelling lookup before you commit. |

Two dictionaries: the main dictionary and a **personal dictionary** you add to as you go, for names
and technical terms; both are checked [WS4 TG p.51 (PDF 80)]. In WordStar 3.0 spelling was a
separate bolt-on product, SpellStar, invoked with `S` from the No-File menu
[WS3 p.1-10 (PDF 26)].

### 7.5 Non-printing comment lines

[WS4 p.134 (PDF 163)]

Type `..` or `.IG` followed by text. The line is visible while editing and never prints. The
manual's suggested uses are notes to yourself: which print wheel to load, when the document was
created, who processed it, what formatting commands were used. Word wrap does not touch dot
commands so the line may be any length; repeat the marker to continue onto another line.

Sawyer singles this out — a note you cannot fail to see during revision, unlike a hidden annotation
[Sawyer]. For MarkStar the analogue is obvious: an inline comment syntax that renders visibly in the
editor and is stripped on export.

### 7.6 Shorthand (`Esc`)

[WS4 p.238 (PDF 265)]

`Esc` plus one character expands to a stored string — **up to 36 user-definable macros** for
frequent words, phrases, or command sequences, usable both while editing and at the Opening Menu.
Built-ins include:

```
=================================== S H O R T H A N D ===================================
 ? display and/or change definitions      = result from last ^QM or ^UM math
 @ today's date                           . last ^QM math equation
 ! current time                           $ formatted number
 C Center        S Sincerely       M Memo        T Transpose Word    P Previous Paragraph
 ^J help
```

`Esc @` (today's date) and `Esc T` (transpose word) are the kind of thing writers use constantly.

### 7.7 Repeat, insert mode, screen redraw

- `^QQ` **repeats a command** continuously; speed controlled with digits as with `^QW`
  [WS4 p.231 (index)].
- `^V` or `Ins` toggles **insert mode** [WS4 p.177 (index)].
- `^N` splits the line at the cursor without moving it [WS4 TG p.93 (PDF 122)].
- `^\` **redraws the screen**, usable while editing or at the Opening Menu
  [WS4 p.128 (PDF 157)].
- `^R` at a prompt **restores the previous answer** to that prompt [WS4 p.228 (index)] — with
  `^S`/`^D` character editing, `^Y` clear entry, `^F` show file directory, and `^U` cancel, WordStar
  had a full line editor at every prompt [WS3 p.1-6 (PDF 22)].

### 7.8 Math

`^QM` opens a **calculator**; `^KM` totals the numbers in a marked block; results are inserted with
`Esc =` or `Esc $` [WS4 p.120 (PDF 149); p.124–126].

---

## 8. jstar: JOE's WordStar emulation

`sources/jstarrc` is the keymap from the locally installed `joe` package. jstar is the most widely
deployed living WordStar emulation and Sawyer cites it as evidence the interface outlived the
product [Sawyer]. It is a useful sanity check on which commands survive translation to a modern
terminal editor — **but MarkStar cannot adopt it wholesale**, because jstar reassigns several `^K`
keys to window management.

### 8.1 Commands jstar keeps faithfully

| Feature | Both |
|---|---|
| Cursor diamond | `^E` `^S` `^D` `^X` |
| Word motion | `^A` `^F` |
| Scroll line / page | `^W` `^Z` / `^R` `^C` |
| Line and file bounds | `^QS` `^QD` `^QE` `^QX` `^QR` `^QC` |
| Mark block | `^KB` `^KK` |
| Block copy / move / delete / write | `^KC` `^KV` `^KY` `^KW` |
| Insert a file | `^KR` |
| Numbered markers | `^K0`–`^K9` set, `^Q0`–`^Q9` go |
| Go to block ends | `^QB` `^QK` |
| Find / replace / repeat | `^QF` `^QA` `^L` |
| Reformat paragraph | `^B` |
| Delete char / word / line / to EOL | `^G` `^T` `^Y` `^QY` |
| Undo | `^U` |
| Insert-overtype toggle | `^V` |
| Split line | `^N` |
| Save and exit | `^KX` |
| Quit | `^KQ` |
| Help | `^J` |
| Status | `^Q?` |
| Math | `^QM` |
| **Previous position** | `^QP` |

### 8.2 Where jstar diverges — the traps

| Key | WordStar 4 | jstar |
|---|---|---|
| `^KD` | Save **and close to Opening Menu** | Save (identical to `^KS`) |
| `^KS` | Save **and resume** | Save |
| `^KE` | **Rename** a file | **Edit** (open) a file |
| `^KO` | **Copy** a file | **Split window** |
| `^KL` | Change logged **drive/directory** | Mark **line** |
| `^KT` | — | Shrink window |
| `^KG` | — | Grow window |
| `^KN` / `^KP` | Column mode / print file | Next window / previous window |
| `^KI` | Column replace | Explode window |
| `^KH` | **Hide** block markers | Return (in menu context); help toggle |
| `^KZ` | — | Shell |
| `^KA` | — | **Center line** (WordStar uses `^OC`) |
| `^QI` | Go to **page** number | Go to **line** number |
| `^Q?` | Character count to cursor | Show status |

**The critical loss: jstar has no distinct save-and-resume versus save-and-close.** `^KD` and `^KS`
are the same command. It also drops the entire `^O` onscreen-format layer (`^O` opens JOE's mode
menu instead), all dot commands, all print controls, column blocks, and file operations on other
files. Those are precisely the writer-facing features MarkStar exists to bring back.

### 8.3 jstar's genuine improvements, worth stealing

- **`^K=` — "goto next position in position history."** jstar generalizes WordStar's one-step `^QP`
  into a **navigable position ring**: `^QP` steps back, `^K=` steps forward. This is the single best
  idea in the file and directly addresses the `^QP` limitation noted in §3.3.
- **`^Q[` / `^Q]` — go to matching bracket.** Useful in Markdown for link and fence matching.
- **`^K/` — filter block through an external command.** Pipe a selection through a shell command and
  replace it with the output. For a Markdown editor this is enormously powerful (sort a list, run a
  formatter, pipe through a CLI).
- **`^KT`-style word marking:** the sequence `rtarw,prevword,markb,nextword,markk` bound to `^KT`
  marks the word under the cursor in one keystroke.
- `^[c` center, `^[t` transpose words, `^[!`/`^[@` insert current time/date — the same instincts as
  WordStar's Shorthand menu.
- The status line hint mechanism: jstar's `-xmsg` displays
  *"Type Ctrl-K Q to exit or Ctrl-J for help"* on startup, and `-rmsg` keeps
  `Ctrl-J for help` permanently in the right of the status line. That is the footer-format hint
  pattern, already proven.

---

## 9. What made WordStar beloved by writers

Distilled from Sawyer's essay; full digest with attributions in
`sources/sawyer-wordstar-essay-notes.md`. The essay is copyrighted, so what follows is his argument,
not his prose.

**1. The hands never leave the home row.** The design principle is that the most-used functions must
be the cheapest to physically execute. Cursor motion is the `^E ^S ^D ^X` diamond under the left
hand; the extended motions cluster around it (`W E R` above, `A S D F` across, `Z X C` below); the
two heaviest prefixes, `^J` help and `^K` block-and-file, sit under the strongest fingers of the
right hand. Backspace is `^H`, not a reach to the corner of the keyboard. The result is that
**composing and revising are the same physical activity** — there is no "editing mode" you enter by
reaching for a mouse, a cursor pad, or a function key. Sawyer's charge against WordPerfect and Word
is precisely that they break the typing trance to make you navigate.

**2. The metaphor is a manuscript, not a typed page.** Competitors emulated a sheet of paper coming
out of a typewriter. WordStar emulated a writer marking up longhand. Everything downstream follows
from that choice.

**3. Marking is separated from acting.** You mark a block's beginning, keep writing for an hour,
mark the end when you get there, and decide later what to do with it. Contemporary word processors
demanded a rigid sequence — decide the operation, mark, execute, return. Because WordStar's block
markers are just positions in the text, the selection is a durable object you can navigate to
(`^QB`, `^QK`) rather than a fragile highlight destroyed by the next keystroke.

**4. The program never loses your place.** `^KS` saves and puts you back exactly where you were.
`^QP` returns you to where you were before the last command. `^QV` returns you to the last find or
the last block. Ten numbered markers (`^K0`–`^K9` / `^Q0`–`^Q9`) let you tie down the places you
keep coming back to. For a novelist moving between chapter three and the outline at the end of the
file, this is the whole ballgame.

**5. Block operations work on files.** `^KW` writes the selection out as a new file; `^KR` reads any
file in at the cursor. The clipboard is the filesystem, so restructuring a book — pulling a scene
out, parking it, dropping it into another chapter — is a first-class operation rather than a
copy-paste between windows.

**6. Notes to yourself live in the text and never print.** A line beginning `..` is visible while you
edit and gone at print time. You cannot overlook a revision note the way you can overlook a hidden
comment.

**7. Find that behaves the way a writer expects.** Whole-word matching (`W`), case-insensitivity
(`U`), backward search (`B`), nth-occurrence, and align-after-replace (`A`). Sawyer's specific
complaint about WordPerfect is that it could not find a word without also matching it inside longer
words.

**8. The program gets out of the way as you learn.** Help levels 3 to 0 progressively strip menus,
prompts, and finally the status line. Better still, at level 2 the menus are **timing-based**: hesitate
after `^K` and the menu appears; type `^KB` briskly and it never draws. The novice and the expert
use the identical keystrokes.

**9. The tool adapts to the writer.** Hundreds of settings, down to which punctuation marks
word-movement skips over and whether the status line updates instantly or only when you pause.

**10. It was reliable.** Chabon's line — *"It never crashed, and it never failed, and I loved it
immoderately"* — is the quiet foundation under everything else. Clarke, Martin, Rice, Chabon, and a
long list of working SF writers stayed on a dead product for decades because the alternative was
worse at the one job that mattered.

---

## Candidate features for MarkStar

A flat, feature-first inventory of every discrete WordStar capability a modern Markdown writing app
could plausibly want. Phrased as capabilities rather than keystrokes, for use as the input to a
feature-parity matrix. Hardware-era items (printer drivers, pitch, sheet feeders, phantom
space/rubout, drive letters, form-feed strings, ribbon colours) are excluded; print-formatting
concepts that map to Markdown or export are kept.

### Startup and file management

- Opening screen listing every available action as a single labelled keystroke
- Live directory listing on the opening screen, with file sizes and free space
- Open a file by moving the cursor onto its name in the directory listing
- Scroll a directory listing that is longer than the screen
- Toggle the directory listing on and off
- Change the working directory
- Open a file for full formatting versus open a file as plain text
- Create a new file by naming one that does not exist, with a confirm prompt
- Rename a file without leaving the editor
- Copy a file without leaving the editor
- Delete a file without leaving the editor, including by wildcard pattern
- Mark a file read-only / protected, with the UI hiding commands that would modify it
- Run a shell command without leaving the editor
- Report memory or resource usage on demand
- Quit to the shell
- Hide irrelevant file types from the file listing

### Saving and session lifecycle

- Save and continue editing at the exact same cursor position
- Save and close, returning to the opening screen
- Save and exit the application
- Abandon all changes since the last save, with confirmation
- Automatic backup of the previous version on every save
- Save and immediately export/print in one command
- Warn when the file has changed on disk underneath the editor

### Cursor motion

- Home-row cursor diamond for up / down / left / right
- Move by word, left and right
- Move to start and end of line
- Move to top and bottom of the visible screen
- Move to beginning and end of document
- Scroll by line without moving the cursor in the text
- Scroll by screen
- Continuous self-propelled scroll with live speed control (a reading mode)
- Screen-by-screen jump to the start or end of the document
- Jump to a page or line number
- Jump forward or backward to the next occurrence of a single character

### Position memory

- Return the cursor to its position before the last command
- Return to the location of the last find match
- Return to the location of the last marked block
- Ten numbered place markers, set and jumped to by digit
- Move a marker by re-setting it; remove a marker by re-issuing it in place
- Persist place markers across editing sessions (WordStar did *not* — a deliberate upgrade)
- Full backward and forward position history ring (from jstar, generalizing return-to-previous)

### Selection and blocks

- Mark the start of a block and the end of a block as independent, persistent acts
- Keep editing indefinitely between marking the start and the end
- Jump to the start or end of the marked block
- Move the block boundaries by re-marking
- Copy, move, and delete the marked block
- Hide block highlighting, with hiding acting as an accidental-edit interlock
- Write the marked block out to a new file
- Insert another file into the document at the cursor
- Insert the last-saved version of the current file into itself
- Rectangular / column selection
- Column replace mode: overwrite at the destination and leave a gap at the source, or push text aside
- Total the numbers inside a selection and insert the result
- Convert the selection to upper or lower case
- Filter the selection through an external command and replace it with the output (from jstar)
- Mark the word under the cursor in one keystroke (from jstar)

### Find and replace

- Find a string, leaving the cursor at the match and returning to normal editing
- Find and replace with per-occurrence confirmation
- Repeat the last find, or the last find-and-replace, with one keystroke
- Whole-words-only matching
- Case-insensitive matching
- Backward search
- Wildcard character matching, opt-in so the wildcard character is otherwise literal
- Jump to the nth occurrence / replace exactly n occurrences
- Replace globally from the top of the document
- Replace through the rest of the document from the cursor
- Replace without confirming each occurrence
- Reflow each affected paragraph automatically after replacement
- Search for control characters, line endings, and formatting marks via a literal-next prefix
- Configurable default search options
- Interrupt a running find or replace

### Editing and text manipulation

- Delete character at cursor, character before cursor, word, line
- Delete to end of line and to beginning of line
- Delete forward to a specified character
- Restore the last deletion, inserting it **at the cursor** rather than where it came from
- Repeatedly re-insert the last deletion (delete-once, paste-many)
- Warn before a deletion too large to be recoverable
- Insert / overtype toggle
- Split the line at the cursor without moving the cursor
- Repeat any command continuously with live speed control
- Universal interrupt key that cancels prompts, searches, reflows, exports, and long motions
- Prompt-line editing with restore-previous-answer, clear-entry, and cancel
- Transpose adjacent words
- Insert today's date and current time

### Formatting and layout

- Reflow the current paragraph to the current margins
- Reflow from the cursor to the end of the document, interruptibly
- Set left and right margins interactively
- Temporarily release the margins
- Temporary (hanging) indent that survives until the paragraph ends
- Paragraph first-line indent
- Centre the current line between margins
- Toggle justified versus ragged-right
- Toggle word wrap
- Set line spacing
- Set and clear tab stops, including decimal-aligned tabs
- Visible ruler line showing current margins and tabs
- Adopt the current line's layout as the ruler
- Embed a ruler in the document so a layout change travels with the text
- Mark a region as never-reflow, to protect tables and code
- Hyphenation assistance during reflow, offering each candidate word with manual placement
- Soft hyphens that print only when they land at a line end
- Non-breaking space so a phrase is never split across lines

### Display

- Toggle display of inline formatting marks
- Preview mode hiding all markup, which also makes the buffer read-only while previewing
- Toggle display of invisible characters such as soft spaces
- Per-line status gutter distinguishing hard line endings from soft wraps
- Per-line status gutter flagging page breaks, structural lines, end-of-file, and overlong lines
- Flag unrecognised directives in the gutter while still excluding them from output
- Redraw the screen on demand

### Document structure and export

- Inline author comments visible while editing and stripped on export
- Force a page break
- Conditional page break keeping n lines together
- Headers and footers, multi-line, with their own margins
- Page numbering, with the ability to set the starting number, suppress it, and resume it
- Top, bottom, and left-offset page margins
- Include another file at export time (file chaining) with continuous page numbering across files
- Build a whole manuscript from a list of component files
- Bold, italic, underline, strikethrough, superscript, subscript
- Mark index entries inline and generate an index
- Generate a table of contents
- Mail-merge / templating: variables filled from a data file or prompted at export time
- Conditional inclusion of content at export time
- Export to a file rather than to a device

### Assistance, feedback, and configuration

- Progressive help levels that strip menus, then prompts, then the status line
- Menus that appear only when the user hesitates after a prefix key, and never when typed quickly
- Contextual help for any individual command, reached from that command's menu
- Help for the screen layout itself and for the markup syntax
- Persistent hint in the status line telling the user how to get help and how to exit
- Character or word count from the start of the document to the cursor, as a progress indicator
- Full word, line, and character count for the document
- Aggregate word count across multiple files of a single manuscript
- Spell-check the rest of the document from the cursor
- Spell-check just the word at the cursor
- Look up the spelling of a typed word without inserting it
- Personal dictionary alongside the main dictionary
- User-defined keyboard macros expanding a short sequence into text or commands
- Built-in expansions for date, time, and common phrases
- Calculator available while editing
- Configurable defaults for margins, justification, word wrap, help level, and search options
- Configurable word-motion behaviour (which punctuation is skipped)
- Configurable status-line update behaviour

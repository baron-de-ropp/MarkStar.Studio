# Robert J. Sawyer, "WordStar: A Writer's Word Processor" — factual digest

**Source:** <https://www.sfwriter.com/wordstar.htm> — copyright 1990, 1996 Robert J. Sawyer.
**Status:** This is a factual digest (claims, commands, rationale), not a reproduction. The essay
text is copyrighted; read it at the source URL. Everything below is a paraphrase of Sawyer's
technical and design claims, recorded here so MarkStar can act on the reasoning.

Sawyer is a Hugo and Nebula winner who wrote his novels in WordStar and argued publicly for it
long after the industry moved on. The essay is the canonical statement of *why* the WordStar
interface suits writers specifically, as opposed to typists, clerks, or office workers.

---

## 1. The touch-typist argument

The core claim: **the most-used functions must be the cheapest to physically execute**, and on a
touch-typist's keyboard that means the home row, not function keys or a mouse.

- Cursor movement is the `^E ^S ^D ^X` **diamond** under the left hand:

  ```
      E
    S   D
      X
  ```

- The extended cursor commands cluster around that diamond: `W E R` above, `A S D F` in the middle,
  `Z X C` below. Every motion command is within one finger-hop of the resting position.
- `^J` (help) and `^K` (block and file) sit under the two strongest fingers of the right hand on the
  home row.
- Sawyer's criticism of WordPerfect: it forces a touch typist to leave the home row constantly, and
  its operations are strictly sequential (press function key, choose a sub-function, move to the
  numeric keys, re-orient to home row).
- His criticism of Word: leaving home row just to reach `Bksp`, plus "layers of menus."
- Both, he argues, force the writer to switch between *writing mode* and *editing mode* by reaching
  for the cursor pad, the function keys, or a mouse. WordStar never makes you leave the keyboard's
  center, so composing and revising are the same physical act.

Historical note he gives: WordStar was released in 1978 by Seymour Rubinstein and Rob Barnaby,
before keyboards were standardized. Many machines had no arrow keys, function keys, Tab, Insert,
Delete, Backspace, or Enter. The control-key-only design was born of necessity and turned out to be
the right design for writers. WordStar even shipped `SWITCH.COM` to swap CapsLock and Ctrl.

## 2. Commands Sawyer names explicitly

| Command | What he says it does |
|---|---|
| `^O` `^Q` `^P` `^K` `^J` | prefix menus: onscreen format, quick, print, block/file, help |
| `^E ^S ^D ^X` | cursor up / left / right / down |
| `^A` `^F` | word left / word right |
| `^W` `^Z` | scroll up / down one line |
| `^R` `^C` | scroll up / down one page |
| `^QE ^QS ^QD ^QX` | jump to top / left / right / bottom of screen |
| `^QW` `^QZ` | scroll continuously up / down |
| `^QR` `^QC` | jump to top / bottom of document |
| `^QB` `^QK` | jump to start / end of marked block |
| `^QV` | jump to previous block location |
| `^QP` | jump to previous cursor position |
| `^K0`–`^K9` | set bookmarks 0–9 |
| `^Q0`–`^Q9` | jump to bookmarks 0–9 |
| `^H` | backspace, without leaving home row |
| `^KU` | (WS 7.0) toggle between two marked blocks |

## 3. The "long-hand page" metaphor

Sawyer's second structural argument: competitors emulate a *typed page*; WordStar emulates a
*manuscript being revised by hand*. Consequences he draws:

- **Blocks can be marked without committing to an action.** Mark a block's beginning, keep writing
  for hours, mark the end later, then decide what to do with it. WordPerfect (at the time) demanded
  a strict sequence: decide cut or copy, mark begin, mark end, move cursor, execute, return.
- **Multiple marked blocks can coexist** — separate marked blocks in each editing window, and in
  7.0 two per window toggled with `^KU`.
- **Ten bookmarks** you can drop and return to freely, which is how you navigate a novel-length
  document rather than a memo.
- **Notes to self that do not print.** A line beginning `..` (e.g. `.. check date of birth`) stays
  visible while editing and vanishes at print time, so a revision note cannot be silently missed the
  way a hidden annotation can.
- **Find that respects word boundaries.** He claims WordStar's find "runs circles around
  WordPerfect's," whose search could not find a single word without also matching the same string
  embedded inside longer words.

Summary line of the philosophy: WordStar puts **the writer in control, not the program**, letting
thoughts be captured before they "evaporate into the ether."

## 4. Customization

He stresses that WordStar exposes hundreds of settings, including:

- which punctuation characters word-movement jumps over,
- help verbosity (the help levels),
- whether the status-line column/inch indicator updates instantly or only when you pause.

His principle: **the writing tool must adapt to the writer, not the other way around.**

## 5. Named endorsements he collects

- **Arthur C. Clarke** — six books in the works, "all through WordStar."
- **George R. R. Martin** — "I use WordStar. It does everything I want."
- **Anne Rice** — "WordStar was magnificent... Microsoft Word is pure madness."
- **Michael Chabon** — "It never crashed, and it never failed, and I loved it immoderately."
- **Edo van Belkom** — "A great system, especially compared to MS Word."

Other working SF writers he lists as users: Roger MacBride Allen, Gerald Brandt, Jeffrey A. Carver,
David Gerrold, Terence M. Green, James Gunn, Matthew Hughes, Donald Kingsbury, Eric Kotani,
Paul Levinson, Vonda McIntyre, Kit Reed, Jennifer Roberson.

## 6. The interface's afterlife

Sawyer notes the WordStar keystroke set was adopted by dBase, SuperCalc, SideKick, TAPCIS, OzCis,
Aladdin, Xtree Pro, **Joe's Own Editor (jstar)**, VDE, and the MS-DOS 5.0+ editor — evidence the
design was worth copying independent of the product.

---

## Relevance to MarkStar

The four ideas worth stealing wholesale, in Sawyer's order of emphasis:

1. Every frequent command reachable without leaving the home row; no chords, no reaching.
2. Marking is decoupled from acting — a selection is a persistent, named thing, not a transient drag.
3. Position memory is a first-class feature (`^QP`, `^QV`, ten numbered markers), because long
   documents are navigated by returning, not by scrolling.
4. Non-printing author notes live inline in the text, visible while editing, gone on export.

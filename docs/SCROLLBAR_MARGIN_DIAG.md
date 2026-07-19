# Diagnostic handoff: Prose editor scrollbar vs 5-column margins

**Date:** 2026-07-17  
**Repo:** `Applications/prose` (Gitea: `https://source.ryanderopp.com/daudzegir/prose`)  
**Stack:** Python 3.12, **Textual 8.2.8**, custom `MarkStarTextArea(TextArea)`  
**Main UI file:** `src/prose/app.py` (class `MarkStarApp`, CSS in `CSS = """..."""`)  
**Goal of this doc:** Another model/engineer can fix layout **without** re-deriving the chat history.

---

## 1. Desired geometry (success criteria)

Terminal width `W` columns. All coordinates are 0-based column indices from the left of the **app content** (full terminal cell grid).

```
Column:  0    5                    W-5   W-4 … W-2   W-1
         |----|--------------------|----….----|--------|
           5     prose / rules /      4 empty     1-col
         left    metrics content      gap         vertical
         margin  share the same                   scrollbar
                 RIGHT edge at W-5                FLUSH to
                                                  terminal
                                                  right edge
```

### Must all be true at once

| Element | Left edge | Right edge of **content** | Scrollbar |
|---------|-----------|---------------------------|-----------|
| Top horizontal rule (`#tab-rule`) | col 5 | col **W-5** | n/a |
| Bottom horizontal rule (`#status-rule`) | col 5 | col **W-5** | n/a |
| Footer metrics (`#support-metrics`, right-aligned) | — | text ends at col **W-5** | n/a |
| Footer key hints (`#support-hints`) | starts ~col 5 | — | n/a |
| **Editor body text** (wrapped prose) | col 5 | last text cell at col **W-5** | — |
| **Vertical scrollbar** on editor | — | — | occupies col **W-1** only (1 cell wide), **flush** to the terminal’s right edge |

**Note:** User clarified right “5-col margin” as: **4 empty columns + 1 scrollbar column** = 5 from the window edge. Rules already look correct with `padding: 0 5`. Editor body does **not**.

### Explicit non-goals

- Do not reintroduce a “card” border around the editor.
- Do not make the scrollbar thick (must stay **1 cell** wide).
- Do not solve by hiding the scrollbar.
- Zen max-width 120 is a **later** product feature; for this bug, full-width terminal is fine as long as the **5 / (W-5) / scrollbar** relationship holds.

---

## 2. Observed failures (regression loop)

We have oscillated between two broken states. The handoff is to achieve **both** constraints simultaneously.

| Attempt | Editor layout idea | Result |
|---------|-------------------|--------|
| A | `#editor { padding: 0 5; }` full width | Text + margins OK-ish; **scrollbar NOT flush** (inset from terminal right) |
| B | Left gutter widget width 5 + `#editor { padding: 0; width: 1fr }` | **Scrollbar flush**; text runs **into** the scrollbar (no right content inset) |
| C | Left gutter 5 + `#editor { padding: 0 4 0 0; }` (current) | Intended: text ends at W-5, scrollbar at W-1. **User reports scrollbar still not flush** (or not against the edge they care about) |

**Current user report (latest):**  
> “now the scrollbar is not against the left edge of the terminal”  

Interpret as almost certainly **right** edge (entire conversation is about the vertical scrollbar on the right). If they literally mean left, also check that the left gutter isn’t pushing the whole editor including a mis-docked bar.

**Previous user report:**  
> Rule lines and footer text are correct; **body prose still flows right up against the scrollbar**.

---

## 3. Current DOM structure (relevant)

```text
Vertical#main
├── Vertical#tab-strip          padding: 0 5
│   ├── Static#tab-pad-top
│   ├── Static#tab-label
│   └── Static#tab-rule         filled with "─" * laid-out width
├── FindBar#find-bar
├── Horizontal#editor-row       width 100%, height 1fr
│   ├── Static#editor-left-pad  width: 5
│   └── MarkStarTextArea#editor    width: 1fr, padding: 0 4 0 0, scrollbar-size-vertical: 1
└── Vertical#bottom-chrome      dock: bottom
    ├── Horizontal#status-rule-row   padding: 0 5
    │   └── Static#status-rule       "─" * width
    ├── Static#support-pad-top
    ├── Horizontal#support-row       padding: 0 5
    │   ├── Static#support-hints     width 1fr
    │   └── Static#support-metrics   width auto, right-aligned
    └── Static#support-pad-bottom
```

Rules are redrawn in `MarkStarApp._update_prose_rules()` after layout using `rule.size.width` and `"─" * width`.

---

## 4. Current CSS (copy from app — may drift; re-read file)

Key bits as of commit around `98a8147` / `a9e59fb` / `5674b9a` lineage:

```css
#tab-strip { padding: 0 5; }

#editor-row { height: 1fr; width: 100%; }
#editor-left-pad { width: 5; height: 1fr; }
#editor {
  width: 1fr;
  height: 1fr;
  padding: 0 4 0 0;   /* right pad 4 + scrollbar 1 ≟ 5-col right inset */
  scrollbar-size-vertical: 1;
  scrollbar-size-horizontal: 0;
  /* muted near-invisible scrollbar colors… */
}

#status-rule-row { padding: 0 5; }
#support-row { padding: 0 5; }
```

---

## 5. Textual layout facts (8.2.8) that matter

From `textual/widget.py` (this install):

1. **Scrollbar is arranged on the widget’s outer `region`**, split from the **right** of that region (`_arrange_scrollbars` / `_get_scrollable_region` use `region.split_vertical(-scrollbar_size_vertical)`).

2. **Content region** is roughly:
   - `content_region = region.shrink(padding+border)`
   - `scrollable_content_region = content_region.shrink(scrollbar_gutter)`

3. Empirically for the user, **`padding-right` on the same widget that owns the scrollbar** caused the **scrollbar to no longer sit on the terminal’s right edge**. That is why we introduced `#editor-left-pad` instead of `padding-left: 5` only, and tried `padding-right: 4` for text inset.

4. **Hypothesis for latest breakage:** With  
   `Horizontal[ left pad 5 | editor 1fr ]`,  
   the editor’s outer region is only `W-5` wide, so the scrollbar is flush to the **editor’s** right edge, which is the terminal’s right edge **only if** the Horizontal truly spans the full width and nothing else eats columns. If something (Footer chrome, dock, double padding, or `1fr` mis-measure) shrinks `#editor-row`, the scrollbar will sit **inset** from the terminal edge.

5. **Competing hypothesis:** `padding: 0 4 0 0` on `#editor` still participates in gutter math such that the scrollbar is laid out **inside** the padded box (inset by 4), undoing flush-right.

---

## 6. Constraints the next fixer must not violate

1. **Scrollbar:** 1 cell wide, visually near-invisible until hover, **column W-1** (flush right).
2. **Prose text wrap width:** last character column of a full-width line should be **W-5** (same as rule end).
3. **Rules / footer metrics:** already correct with `padding: 0 5` — do not “fix” them by making them full-bleed again.
4. Prefer CSS/layout structure over fighting `TextArea` internals; subclass `MarkStarTextArea` is only for key handling today.

---

## 7. Suggested investigation steps

1. **Measure in a pilot** (`app.run_test(size=(100, 30))` or real `on_resize` logging):
   - `app.size.width` → `W`
   - `#editor-row.size.width`
   - `#editor-left-pad.size.width` (expect 5)
   - `#editor.size.width` (expect `W-5` if row is full width)
   - `#editor.region` / `content_region` / `scrollable_content_region` if accessible
   - Screen coordinates of the vertical scrollbar widget: `editor.vertical_scrollbar.region`

2. **Prove scrollbar column:**  
   `scrollbar.region.x + scrollbar.region.width == app.size.width` (or screen width).

3. **Prove text column:**  
   Soft-wrap width / `scrollable_content_region.width` should be `W - 5 - 5` = `W - 10`  
   (left margin 5 + right margin 5), **or** `W - 5 - 4 - 1` if right margin is 4 pad + 1 scrollbar outside content.

4. **A/B test pure layouts** (minimal CSS, no theme noise):

   **Layout α — padding only (full-width editor):**
   ```text
   MarkStarTextArea#editor { width: 1fr; padding: 0 5; scrollbar-size-vertical: 1; }
   ```
   Measure whether scrollbar is at `W-1` or `W-1-5`.

   **Layout β — gutters outside TextArea:**
   ```text
   Horizontal
     Static left w=5
     TextArea padding=0 scrollbar=1  w=1fr
     Static right w=5   ← this almost always makes scrollbar NOT flush
   ```

   **Layout γ — left gutter only + content max width:**
   ```text
   Horizontal
     Static left w=5
     TextArea padding-right=4 (or 5) scrollbar=1 w=1fr
   ```
   Measure scrollbar x-position vs text width.

5. **If Textual always insets scrollbar with padding-right:** implement **right margin without padding on the scrollable widget**, e.g.:
   - custom layout / `max_width` on an inner container, or
   - wrap document view (if API allows), or
   - accept a dedicated full-height right gutter **behind** or **under** a docked scrollbar (harder).

---

## 8. How to run

```bash
cd /path/to/prose
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
prose /tmp/sample.md
pytest -q
```

Manual check with a wide terminal (e.g. ≥ 100 cols):

1. Paste a long unwrapped line of `X`s longer than the window.
2. Confirm soft-wrap turns at the same column as the end of the `─` rules.
3. Confirm the thin scrollbar is in the last column of the terminal (no blank column to its right).
4. Confirm footer `Ln … │ words │ CommonMark` right edge matches the rule end.

---

## 9. Definition of done (acceptance)

- [ ] Vertical scrollbar occupies the **last column** of the app (no empty column to its right).
- [ ] Wrapped prose, top rule, bottom rule, and right-aligned footer metrics share the **same content right edge** (column **W-5**).
- [ ] Left content edge remains **column 5**.
- [ ] Scrollbar remains 1 cell wide and low-contrast when not hovered.
- [ ] `pytest` still passes; no regression to menu (F9) or save/quit flows.

---

## 10. Files to touch

| File | Why |
|------|-----|
| `src/prose/app.py` | `CSS`, `compose()` (`#editor-row`), possibly `_update_prose_rules` |
| Optionally new `src/prose/ui/editor_layout.py` | If a dedicated layout widget is cleaner |

Do **not** need to change `Document` / `Workspace` for this bug.

---

## 11. One-paragraph problem statement (pasteable)

> In a Textual 8.2.8 app, we need a full-height `TextArea` whose **vertical scrollbar is flush against the right edge of the terminal** (1 column wide), while the **wrapped text**, **horizontal rule lines**, and **right-aligned footer metrics** all share a content box inset by **5 columns on the left and 5 on the right** (i.e. text/rules end at column W-5; scrollbar at W-1). Using `padding: 0 5` on the TextArea insets the scrollbar. Using a left-only gutter makes the scrollbar flush but lets text run into the scrollbar. Using `padding-right: 4` on a left-guttered TextArea was the last attempt and still fails flush-right according to the user. Find a layout/CSS structure that satisfies both constraints simultaneously and document the measured column geometry.

---

## 12. Contact / product context

- App name: **Prose** (terminal Markdown writer)
- Design spec: `docs/PROSE_V0.1_DESIGN_SPEC.md` (margins 5 / zen 120 mentioned; zen not required for this fix)
- Prefer minimal, reversible CSS/layout change over a rewrite

---

## 13. ADDENDUM — RESOLVED (2026-07-17)

### Root cause (proven from Textual 8.2.8 source, not inferred)

Hypotheses 4 and 5 in §5 collapse into one mechanism. In `textual/_compositor.py:584`:

```python
container_region = region.shrink(styles.gutter)
```

where `styles.gutter` = **padding + border** (`textual/css/styles.py:613`). The scrollbar is then carved out of *that already-shrunk region* via `_arrange_scrollbars(container_region)` (`_compositor.py:708`). Consequence: **any right padding on the widget that owns the scrollbar insets the scrollbar by that padding.** Attempt C (`padding: 0 4 0 0`) placed the scrollbar at column W-5 — exactly the user's "not flush" report. No padding value can satisfy §1's constraints; the contradiction is structural.

### Fix applied (`src/prose/app.py`)

The escape hatch is `TextArea.wrap_width` (`textual/widgets/_text_area.py:1225`) — a plain property re-read on every rewrap/resize that controls where *text* soft-wraps, independent of the widget box.

1. **CSS `#editor`:** `padding: 0 4 0 0` → `padding: 0` (scrollbar now flush at W-1), and `scrollbar-gutter: auto` → `stable` (reserves the bar column even when the document fits, so the wrap column never shifts by 1 when the bar appears/disappears).
2. **`MarkStarTextArea.wrap_width` override:** returns `super().wrap_width - 3` (class constant `EXTRA_RIGHT_MARGIN = 3`). The base value already reserves the scrollbar column (via `scrollable_content_region`) plus 1 cursor cell; 3 more blank columns yields the full 5-column right inset, so text ends at the same column as the rules (`padding: 0 5`).

DOM structure (§3) is unchanged — left gutter widget stays.

### Measured geometry (headless pilot, `run_test(size=(100, 30))`)

| Measurement | Value | Constraint |
|---|---|---|
| `#editor.region` | `x=5, width=95` | left edge col 5 ✓ |
| scrollbar region | `x=99, width=1` | flush right, 1 cell ✓ |
| `wrap_width` | 90 | — |
| text last column | 94 | == rule last column 94 ✓ |
| right inset from edge | 5 cols | 4 blank + 1 scrollbar ✓ |

Rendered-screen check: rule row and fully-wrapped `X` rows both end at column 94. `pytest`: 45 passed. All §9 acceptance boxes satisfied except the manual wide-terminal eyeball.

### If this regresses

The load-bearing invariant: `#editor` must have **zero right padding/border**, and the 5-col right text inset must live entirely in `wrap_width`. If a future Textual version changes how `wrap_width` composes (e.g. stops subtracting the cursor cell), re-derive `EXTRA_RIGHT_MARGIN` as `5 − (what the base property already reserves to the right of text)`.

# Chuck's List Builder — Engineer Guide

> The technical almanac. Read this before touching any file in the codebase.

This guide is for developers — anyone modifying, debugging, extending, or
handing off this pipeline. The [README](README.md) covers operator use.
This document covers the *why* behind every technical decision.

---

## Table of Contents

- [Before You Touch Anything](#before-you-touch-anything)
- [Architecture Contracts](#architecture-contracts)
- [File Roles](#file-roles)
- [Path Anchoring](#path-anchoring)
- [The Escape-Then-Linkify Pipeline](#the-escape-then-linkify-pipeline)
- [Date Parsing](#date-parsing)
- [Image Handling](#image-handling)
- [CSV Contract](#csv-contract)
- [CLI Message Tags](#cli-message-tags)
- [Bug History](#bug-history)
- [Open Punch List](#open-punch-list)
- [Engineering Standards](#engineering-standards)
- [What Not to Do](#what-not-to-do)

---

## Before You Touch Anything

1. **Read the existing script in full.** Every file in this repo has a docstring
   that explains its role, contracts, and changelog. Read it.

2. **Commit a working baseline before editing:**
   ```bash
   git commit -am "working baseline before <description>"
   ```

3. **Validate Python syntax after every save:**
   ```bash
   py -m py_compile ChucksBulletin\bulletins\compile_bulletin.py && echo OK
   ```

4. **Test against real CSVs and a real issue date.** The bugs in this project's
   history were almost all caught only when real LibreOffice export data was used.

5. **Do not push to GitHub directly.** Provide code for the operator to paste
   and push manually after local testing.

---

## Architecture Contracts

These contracts must not be broken by any change:

1. **Two separate pipelines — keep them separate.**
   Bulletins and Events share no code, no state, and no intermediate files.
   Do not introduce shared modules, shared base classes, or merged stages.

2. **Preprocess and compile are intentionally separate stages.**
   Preprocess validates and normalizes; compile renders. Never combine them.

3. **Bulletin inclusion rule:** `Received <= issue_date <= Expires`
   **Events inclusion rule:** `Starts <= issue_date <= Expires`
   The Events CSV column is named `Expires`; it maps to `Ends` in `events_data.csv`.

4. **Bulletin section order is fixed. Urgent always first.**
   Non-Urgent sections are sorted by ascending item count after Urgent.
Urgent Bulletins
Housing Opportunities
Swap Market
Local Services & Help
Community Announcements

text

5. **CSV contract:** UTF-8, comma-delimited, `QUOTE_ALL`, Python `csv` with `newline=""`.

6. **Path anchoring:** ALL paths in all scripts use `Path(__file__).resolve().parent`.
Never `os.getcwd()`. Never hardcoded absolute paths.

7. **Date formats accepted (both preprocessors must handle all three):**
```python
DATE_RE_ISO   = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
DATE_RE_SHORT = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2})$")
DATE_RE_LONG  = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
```
All three must be defined at module level. `DATE_RE_LONG` handles the
`M/D/YYYY` format LibreOffice Calc commonly exports.

8. **Asset paths in HTML must use forward-slash URL syntax.** Never Windows
backslashes. Use this helper in both compilers:
```python
from urllib.parse import quote
def to_web_path(path):
    return quote(Path(path).as_posix(), safe="/:._-")
```
Both `href` and `src` for the same image must use the identical normalized path.

9. **Multi-image field contract:** The `Image` column accepts 1–3
pipe-separated filenames. Split on `|` and render one `<img>/<a>` pair
per entry. A 4th pipe-segment triggers `[WARN]` and is dropped.
Never emit `src="img1.png | img2.png"`.

10. **Image paths resolve relative to the pipeline's staging folder root.**
 `ChucksBulletin/` for bulletins, `ChucksEvents/` for events.
 `Images/`, `ChucksBulletin/Images/`, and `ChucksEvents/Images/` are all
 local-only and must never be committed to git.

11. **The `notes` column is never rendered and never written to intermediate CSVs.**
 It exists only in the raw source CSVs as a staff annotation field.

12. **CLI message tags are machine-parseable by design:**
 `[WARN]`, `[ERROR]`, `[REMIND]`, `[AUTO-FIX]`
 This structure supports a future GUI log panel. Do not change the tag format.

---

## File Roles

| File | Role |
|---|---|
| `Chucks_List_Builder.py` | Orchestration entrypoint — calls both pipelines via subprocess |
| `ChucksBulletin/bulletins/preprocess_bulletin_text.py` | Normalize, validate, and date-filter bulletin rows; write intermediate CSV |
| `ChucksBulletin/bulletins/compile_bulletin.py` | Render intermediate bulletin CSV into final HTML email |
| `ChucksEvents/events/preprocess_events_text.py` | Normalize, validate, and date-filter event rows; write intermediate CSV |
| `ChucksEvents/events/compile_events.py` | Render intermediate events CSV into final HTML email |
| `System/SYSTEM_README.md` | Operator guide — keep current after every significant change |
| `System/ENGINEER_GUIDE.md` | This file — technical almanac for developers |
| `System/BUG_LIST.md` | Canonical bug ledger — append new entries; never delete resolved ones |
| `System/config.py.template.py` | Template for local config (config.py itself is git-ignored) |
| `System/logs/` | Timestamped build logs written by `--log-to-file`; git-ignored |

**Generated files (not committed):**
- `bulletins_data.csv` / `events_data.csv` — intermediate CSVs
- `chucks_bulletin_final_output.html` / `chucks_events_final_output.html` — HTML outputs
- `Bulletins.csv` / `Events.csv` — raw source exports from Google Drive

---

## Path Anchoring

Every script resolves all paths from its own location:

```python
SCRIPT_DIR = Path(__file__).resolve().parent
PROJ_DIR   = SCRIPT_DIR.parent   # one level up from bulletins/ or events/
```

For the compilers, `PROJ_DIR` is `ChucksBulletin/` or `ChucksEvents/` —
the staging folder root. Output is written to both the script subfolder
and to `PROJ_DIR` directly so Zoho staging always has the latest file.

**The P1-C bug** was caused by compilers setting `OUTPUT_DIR = PROJ_DIR / "ChucksBulletin"`,
which from inside `ChucksBulletin/bulletins/` resolved to
`ChucksBulletin/ChucksBulletin/`. The fix is `OUTPUT_DIR = PROJ_DIR`.

---

## The Escape-Then-Linkify Pipeline

This is the single most important correctness guarantee in the compilers.
The order must never be reversed.
protect_markdown_links() → extract Label tokens before escaping
↓
html.escape() → escape all remaining < > & " '
↓
linkify_escaped_text() → linkify bare URLs/emails in the now-safe text
↓
restore_markdown_links() → reinsert the pre-built <a> tags

text

**Why this order?** If you linkify before escaping, the `<a href="...">` tags
you just built get their angle brackets escaped into `&lt;a href=...&gt;`.
If you escape before protecting Markdown links, the `[]()` syntax gets
mangled. The protect → escape → linkify → restore sequence handles both.

Bare URL linkification uses a bounded regex — no catastrophic backtracking,
and trailing punctuation is stripped from `href` values before use.

---

## Date Parsing

All three formats must be handled. The most common failure mode in this
project's history was a missing `DATE_RE_LONG` handler — LibreOffice Calc
exports dates as `M/D/YYYY` by default, which caused every row to be
skipped with no error when the handler was absent (Bug 4).

```python
DATE_RE_ISO   = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")       # 2026-06-07
DATE_RE_SHORT = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2})$")   # 6/7/26
DATE_RE_LONG  = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")   # 6/7/2026
```

Two-digit years in `DATE_RE_SHORT` are interpreted as `2000 + YY`.

All three must be defined at module level in both preprocessors.
The parse function must try all three and return `None` (not raise) on
no match, so the caller can emit a `[WARN]` and skip the row gracefully.

---

## Image Handling

### Path normalization

```python
from urllib.parse import quote
def to_web_path(path: str) -> str:
    return quote(Path(path).as_posix(), safe="/:._-")
```

Apply to every path before writing it into `src=` or `href=`.
`safe="/:._-"` preserves path separators and common filename characters.

### Prefix enforcement

If an operator enters `photo.jpg` instead of `Images/photo.jpg`, the
compiler auto-prepends the prefix and emits a `[WARN]`. This is done in
`ensure_images_prefix()` in both compilers.

### Pipe-split contract

```python
raw_entries = [e.strip() for e in image_field.split("|") if e.strip()]
```

This split **must** happen before any path enters `src=` or `href=`.
Bug 6 was caused by passing the unsplit pipe-joined string directly into
the template.

### MAX_INLINE_IMAGES = 3

A 4th entry is dropped with a `[WARN]`. The operator is told to use a
link in the body text for the additional image.

---

## CSV Contract

Every `DictWriter` in this project must use:

```python
writer = csv.DictWriter(
    f,
    fieldnames=FIELDNAMES,
    quoting=csv.QUOTE_ALL,
    lineterminator="\n",
)
```

And every file open for CSV writing must use `newline=""`:

```python
with open(path, "w", newline="", encoding="utf-8") as f:
```

**Why QUOTE_ALL?** Bug 2 was caused by a missing `QUOTE_ALL` on the events
preprocessor. Multi-line cells and cells containing `[]()` Markdown syntax
were written unquoted; the compiler's `MARKDOWN_LINK_RE` failed to match
them on read-back, and links rendered as raw text.

---

## CLI Message Tags

| Tag | Use case | Behavior |
|---|---|---|
| `[WARN]` | Row skipped or field auto-corrected | Includes row, field, value, fix instruction |
| `[ERROR]` | Blocking failure | Pipeline stops; must fix before retrying |
| `[REMIND]` | Per-issue customization not set | Informs operator; does not stop pipeline |
| `[AUTO-FIX]` | Safe automatic correction applied | Logged; operator can review |

These are written to `stderr` by preprocessors and compilers so the
orchestrator (`Chucks_List_Builder.py`) can capture and forward them.
The Builder forwards `[REMIND]` lines from stderr as `WARNING` level logs.

---

## Bug History

All resolved. Do not reintroduce.

| Bug | Root Cause | Fix |
|---|---|---|
| **Bug 1** — Callouts never prompted | Builder called compilers with no `--callout` arg; operator had no signal to customize | `emit_callout_reminders()` added; `--callout`/`--bottom-callout` wired through entrypoint |
| **Bug 2** — Markdown links rendered as raw text in events email | `preprocess_events_text.py` missing `QUOTE_ALL` on `DictWriter`; `[]()` syntax written unquoted | `QUOTE_ALL` added |
| **Bug 3** — "here" link not rendering | Resolved by Bug 2 fix |
| **Bug 4** — All bulletins skipped; zero-item output exits 0 | `parse_date()` had no `M/D/YYYY` handler; LibreOffice exports `5/21/2026`; every row hit fallthrough | `DATE_RE_LONG` added at module level in both preprocessors |
| **Bug 5** — Windows backslash paths in HTML `src`/`href` | Paths built with `Path` on Windows emit backslashes | `to_web_path()` using `Path.as_posix()` + `urllib.parse.quote` added to both compilers |
| **Bug 6** — Pipe-delimited image field not split before render | Unsplit pipe-joined string passed into `src=` | `build_image_html()` splits on `\|` first |
| **Bug 7** — False-positive Markdown validation errors | Naive parenthesis counting across full Body field fired on valid URLs containing `(` `)` (BurroFest URL) | Replaced with segment-targeted `[label](target)` validation |
| **Bug 8** — `--debug` flag not defined in argparse | `add_argument("--debug", ...)` missing | Added |

---

## Open Punch List

### Priority 1 — Pipeline safety

**P1-C — Nested duplicate staging folders**
Compilers produce `ChucksBulletin/ChucksBulletin/` and `ChucksEvents/ChucksEvents/`
as a side effect of `OUTPUT_DIR` path resolution.
Fix: `OUTPUT_DIR = PROJ_DIR` in both compilers (was `PROJ_DIR / "ChucksBulletin"`).

### Priority 2 — Layout and UX

**P2-A — Section ordering by size (Bulletins)**
After Urgent, sort non-Urgent sections by ascending item count.
Change in `compile_bulletin.py` only.

**P2-B — TOC single-item hiding (both compilers)**
Conditionally suppress per-item TOC entries for sections with exactly one item.
Show the section heading only in those cases.

### Priority 3 — Content quality

**P3-A — Multiple Events grouping**
Rows sharing a title or lead image in "Hosts with Multiple Events" should be
grouped under one heading. Implement after P1 items are resolved.

**P3-B — Bulletin rotation within same-date groups**
When multiple bulletins in the same section share the same `Received` date,
rotate their order across issues so no submitter is always last.
Implement in `compile_bulletin.py` only. CSV-based for now; replace with
SQL at database migration.

**P3-C — "NEW" badge on first-issue entries**
Compare current intermediate CSV against the prior issue's intermediate CSV
(stored in `System/` with issue-date filenames). Items not present in the
prior run receive a `[NEW]` indicator in the HTML.
CSV-diff version for now; replace with SQL query at migration.

### Priority 4 — Deferred (post-database migration)

- P4-A: Interactive stage-confirm loop in CLI
- P4-B: Click-tracking stubs and error trend logging
- P4-C: Full layout/grouping/rotation refinement using SQL queries

---

## Engineering Standards

1. **Full file replacements only.** Provide the complete file for the
   operator to paste. No partial patches or diffs.

2. **Validate syntax after every edit:**
   ```bash
   py -m py_compile <file>.py && echo OK
   ```

3. **Commit working state before every edit session.**

4. **Never emit filesystem paths into HTML.** Always use `to_web_path()`.

5. **Never validate Markdown with raw parenthesis counting.**
   Parse `[label](target)` segments structurally.

6. **`QUOTE_ALL` on every `DictWriter`.** No exceptions.

7. **Split pipe-delimited fields before templating.** Never pass a
   pipe-joined string into `src=` or `href=`.

8. **Zero-item preprocess output that exits 0 is a silent build failure.**
   Exit non-zero when `passing == 0` and `skipped > 0`.

9. **Do not push to GitHub directly.** Provide code; let operator push
   after local testing.

---

## What Not to Do

- Do not redesign toward the database/GUI end state in the current CLI
- Do not replace Zoho Campaigns as the send engine
- Do not collapse Bulletins and Events into one pipeline
- Do not alter the approved visual design (colors, fonts, layout)
- Do not invent abstraction layers not already present
- Do not commit images to git under any circumstances
- Do not use `os.getcwd()` for path resolution
- Do not reverse the escape-then-linkify order

---

*Chuck's List Builder — Engineer Guide*
*Read it. Know it. Then go change things carefully.*
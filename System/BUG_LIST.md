# Chuck's List Builder — Bug Ledger

> Canonical record of all known bugs, their status, and fix summaries.
> Open items are tracked here; resolved items remain as permanent history.
> Do not edit retroactively — append only. Update status in-place when a bug moves.
>
> Source of truth for "what broke and why" across all sessions.
> Cross-referenced with commit history starting 2026-05-30.

---

## Format Reference

| Field | Acceptable values |
|---|---|
| ID | `BUG-NNN` (sequential) |
| Title | One short phrase |
| Status | `Open` / `In Progress` / `Fixed` / `Deferred` |
| Area | File or subsystem name |
| Symptom | 1–2 sentences describing what the operator sees |
| Cause / Fix | Brief explanation; `Approximate` if reconstructed from history |

---

## Resolved Bugs

---

### BUG-001
| Field | Value |
|---|---|
| **ID** | BUG-001 |
| **Title** | Callout boxes never prompted; operator had no signal to customize |
| **Status** | Fixed |
| **Area** | `Chucks_List_Builder.py` |
| **Symptom** | Builder called compilers with no `--callout` or `--bottom-callout` argument. Default text was used silently every issue with no reminder to the operator. |
| **Cause / Fix** | `emit_callout_reminders()` function added to orchestrator. `--callout` and `--bottom-callout` flags wired through entrypoint to both compilers. `[REMIND]` tag emitted when flags are absent so operator sees the default text and the exact flag to override it. |

---

### BUG-002
| Field | Value |
|---|---|
| **ID** | BUG-002 |
| **Title** | Markdown links rendered as raw text in events email |
| **Status** | Fixed |
| **Area** | `ChucksEvents/events/preprocess_events_text.py` |
| **Symptom** | Links written as `[Label](url)` in the Events CSV appeared as literal text in the output HTML rather than as clickable `<a>` tags. |
| **Cause / Fix** | `preprocess_events_text.py` was missing `QUOTE_ALL` on its `DictWriter`. Cells containing `[]()` Markdown syntax were written unquoted; the compiler's `MARKDOWN_LINK_RE` failed to match them on read-back. Fix: `quoting=csv.QUOTE_ALL` added to `DictWriter` in events preprocessor. |

---

### BUG-003
| Field | Value |
|---|---|
| **ID** | BUG-003 |
| **Title** | "here" link not rendering in events output |
| **Status** | Fixed |
| **Area** | `ChucksEvents/events/preprocess_events_text.py` |
| **Symptom** | A specific `[here](url)` Markdown link in an events item failed to render as a hyperlink. |
| **Cause / Fix** | Approximate — root cause was the same missing `QUOTE_ALL` as BUG-002. Resolved by the same fix. |

---

### BUG-004
| Field | Value |
|---|---|
| **ID** | BUG-004 |
| **Title** | All bulletins skipped; zero-item output exits 0 silently |
| **Status** | Fixed |
| **Area** | `ChucksBulletin/bulletins/preprocess_bulletin_text.py` (originally; then both preprocessors) |
| **Symptom** | Running the builder against a real LibreOffice CSV export produced zero items in output. No error was reported; the pipeline exited 0 as if successful, producing a blank-issue HTML. |
| **Cause / Fix** | `parse_date()` had no handler for the `M/D/YYYY` format that LibreOffice Calc exports by default (e.g., `5/21/2026`). Every row hit the fallthrough and was silently skipped. Fix: `DATE_RE_LONG = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")` added at module level in both preprocessors. Additionally, zero-item preprocess output now exits non-zero to prevent a silent blank issue. |

---

### BUG-005
| Field | Value |
|---|---|
| **ID** | BUG-005 |
| **Title** | Windows backslash paths written into HTML `src` and `href` |
| **Status** | Fixed |
| **Area** | `ChucksBulletin/bulletins/compile_bulletin.py`, `ChucksEvents/events/compile_events.py` |
| **Symptom** | Image `src` and `href` attributes in HTML output contained Windows-style backslash paths (e.g., `Images\photo.jpg`). Images failed to load in browsers and Zoho Campaigns. |
| **Cause / Fix** | `pathlib.Path` on Windows emits backslashes. Fix: `to_web_path()` helper added to both compilers using `Path.as_posix()` + `urllib.parse.quote(..., safe="/:._-")`. Both `href` and `src` for the same image now use the identical normalized forward-slash path. |

---

### BUG-006
| Field | Value |
|---|---|
| **ID** | BUG-006 |
| **Title** | Pipe-delimited image field not split before render |
| **Status** | Fixed |
| **Area** | `ChucksBulletin/bulletins/compile_bulletin.py`, `ChucksEvents/events/compile_events.py` |
| **Symptom** | When an item had multiple images separated by `|` in the CSV (e.g., `Images/a.jpg|Images/b.jpg`), the entire pipe-joined string was passed directly into `src=`, producing a broken image tag. |
| **Cause / Fix** | `build_image_html()` in both compilers now splits the `Image` field on `|` before rendering. Each entry gets its own `<img>/<a>` pair. A 4th pipe-segment triggers `[WARN]` and is dropped. |

---

### BUG-007
| Field | Value |
|---|---|
| **ID** | BUG-007 |
| **Title** | False-positive Markdown validation errors on valid URLs |
| **Status** | Fixed |
| **Area** | `ChucksBulletin/bulletins/preprocess_bulletin_text.py` |
| **Symptom** | Bulletin items containing URLs with balanced parentheses in the body (e.g., a BurroFest event URL) triggered `[ERROR]` Markdown validation failures even though the links were correctly formed. |
| **Cause / Fix** | The validator was using a naive parenthesis counter across the entire `Body` field. Any URL containing `(` `)` fired a false positive. Fix: replaced with segment-targeted `[label](target)` structural parsing that validates each Markdown link token individually. |

---

### BUG-008
| Field | Value |
|---|---|
| **ID** | BUG-008 |
| **Title** | `--debug` flag not defined in argparse |
| **Status** | Fixed |
| **Area** | `Chucks_List_Builder.py` |
| **Symptom** | Passing `--debug` on the CLI caused an `unrecognized arguments` error and immediate exit. |
| **Cause / Fix** | `add_argument("--debug", action="store_true")` was missing from the argparse setup. Added. |

---

### BUG-009
| Field | Value |
|---|---|
| **ID** | BUG-009 |
| **Title** | Unicode arrow `→` in preprocess success message crashes Windows console |
| **Status** | Fixed |
| **Area** | `preprocess_bulletin_text.py`, `preprocess_events_text.py` |
| **Symptom** | On Windows with cp1252 console encoding, the preprocess scripts crashed when printing the OK status message containing a literal `→` (U+2192) character. |
| **Cause / Fix** | Replaced `→` with ASCII `->` in both preprocess scripts' success print statements. |

---

### BUG-010
| Field | Value |
|---|---|
| **ID** | BUG-010 |
| **Title** | Non-UTF-8 bytes in subprocess output crash builder on Python 3.14 |
| **Status** | Fixed |
| **Area** | `Chucks_List_Builder.py` |
| **Symptom** | On Python 3.14, the subprocess reader thread raised `UnicodeDecodeError` when compile scripts emitted non-UTF-8 bytes (cp1252 `0xa0` non-breaking spaces from CSV source data). This left `result.stderr` as `None` and crashed the builder after the HTML was already written successfully. |
| **Cause / Fix** | Added `errors="replace"` to `subprocess.run()` to tolerate bad bytes. Added `None` guards on `stdout` and `stderr` before `.strip()`. Returns empty string fallback instead of `None` to caller. |

---

### BUG-011
| Field | Value |
|---|---|
| **ID** | BUG-011 |
| **Title** | `run_stage` return statement displaced outside function body — SyntaxError on import |
| **Status** | Fixed |
| **Area** | `Chucks_List_Builder.py` |
| **Symptom** | Repeated in-place patches to `Chucks_List_Builder.py` caused the `return` statement inside `run_stage()` to be pushed outside the function body, producing a `SyntaxError` at import time and a silent exit-0. Pipeline appeared to run but did nothing. |
| **Cause / Fix** | Full rewrite of `Chucks_List_Builder.py` from scratch to clear the accumulated patch damage. Indentation corrected. |

---

### BUG-012
| Field | Value |
|---|---|
| **ID** | BUG-012 |
| **Title** | `__main__` block called wrong function and used wrong kwarg name |
| **Status** | Fixed |
| **Area** | `Chucks_List_Builder.py` |
| **Symptom** | The bulletin pipeline's `__main__` call invoked `compile_events(...)` instead of `compile_bulletins(...)`, and passed `callout=` instead of the correct parameter name `top_callout=`. Bulletins were never compiled regardless of CLI flags. |
| **Cause / Fix** | Corrected function name to `compile_bulletins(...)` and kwarg to `top_callout=args.callout`. Also fixed a 3-space indent on `parser.add_argument("--callout"...)` that caused an `IndentationError` at import time. |

---

### BUG-013
| Field | Value |
|---|---|
| **ID** | BUG-013 |
| **Title** | Events compiler skipping valid rows due to unrecognized section values |
| **Status** | Fixed |
| **Area** | `ChucksEvents/events/compile_events.py` |
| **Symptom** | Valid event rows with `Section` values of `Single`, `Multiple`, or `Recurring` were silently skipped. Output HTML was empty or nearly empty even with a populated `events_data.csv`. |
| **Cause / Fix** | Approximate — compile_events.py was checking for section values that did not match the actual canonical values coming through from the preprocessor. Fix: updated section grouping logic to accept the canonical section identifiers (`Single Events`, `Hosts with Multiple Events`, `Recurring Events`). |

---

### BUG-014
| Field | Value |
|---|---|
| **ID** | BUG-014 |
| **Title** | Events compiler not accepting `--callout` / `--bottom-callout` CLI flags |
| **Status** | Fixed |
| **Area** | `ChucksEvents/events/compile_events.py` |
| **Symptom** | Passing `--callout` or `--bottom-callout` to the builder had no effect on the events output. Events email always displayed hardcoded default callout text. |
| **Cause / Fix** | `compile_events.py` did not define `--callout` or `--bottom-callout` in its argparse setup. Flags added with safe defaults matching the bulletin compiler pattern. |

---

### BUG-015
| Field | Value |
|---|---|
| **ID** | BUG-015 |
| **Title** | Events TOC structure did not match bulletin TOC — harder to scan |
| **Status** | Fixed |
| **Area** | `ChucksEvents/events/compile_events.py` |
| **Symptom** | The events email TOC used a flat list format rather than the section-heading-with-linked-items structure used in the bulletin. Scanning by section was awkward. |
| **Cause / Fix** | Events compiler TOC rebuilt to match bulletin pattern: section headings are linked anchors, and item titles are listed under each section heading for faster email scanning. |

---

### BUG-016
| Field | Value |
|---|---|
| **ID** | BUG-016 |
| **Title** | `Chucks_List_Builder.py` committed containing shell-command artifact instead of Python source |
| **Status** | Fixed |
| **Area** | `Chucks_List_Builder.py` |
| **Symptom** | File contained a shell command artifact rather than valid Python source. Script failed to execute entirely. |
| **Cause / Fix** | File replaced with correct Python source. |

---

### BUG-017
| Field | Value |
|---|---|
| **ID** | BUG-017 |
| **Title** | Nested duplicate staging folder created on every build |
| **Status** | In Progress |
| **Area** | `ChucksBulletin/bulletins/compile_bulletin.py`, `ChucksEvents/events/compile_events.py` |
| **Symptom** | Compilers produce `ChucksBulletin/ChucksBulletin/` and `ChucksEvents/ChucksEvents/` as a side effect of `OUTPUT_DIR` path resolution. Staging copy ends up nested one level too deep and is not found by Zoho upload workflow. |
| **Cause / Fix** | `OUTPUT_DIR` was set to `PROJ_DIR / "ChucksBulletin"` inside `compile_bulletin.py`. From inside `ChucksBulletin/bulletins/`, `PROJ_DIR` already resolves to `ChucksBulletin/`, so the join creates the nested path. Fix: change `OUTPUT_DIR = PROJ_DIR` in both compilers. **Not yet applied in current codebase.** |

---

## Open Items

---

### BUG-018 (P2-A)
| Field | Value |
|---|---|
| **ID** | BUG-018 |
| **Title** | Bulletin sections not sorted by ascending item count after Urgent |
| **Status** | Open |
| **Area** | `ChucksBulletin/bulletins/compile_bulletin.py` |
| **Symptom** | Non-Urgent bulletin sections appear in CSV order rather than sorted by smallest-to-largest item count. Short sections with one item may appear after long sections, making the email harder to scan. |
| **Cause / Fix** | No sort applied in `compile_bulletin.py`. Fix: after pinning Urgent, sort remaining sections by `len(items)` ascending before rendering. Change confined to `compile_bulletin.py` only. |

---

### BUG-019 (P2-B)
| Field | Value |
|---|---|
| **ID** | BUG-019 |
| **Title** | TOC shows per-item entries for single-item sections |
| **Status** | Open |
| **Area** | `ChucksBulletin/bulletins/compile_bulletin.py`, `ChucksEvents/events/compile_events.py` |
| **Symptom** | When a section contains exactly one item, the TOC shows a redundant sub-entry beneath the section heading. The section heading alone is sufficient for navigation. |
| **Cause / Fix** | TOC generation in both compilers emits item links unconditionally. Fix: conditionally suppress per-item TOC entries when `len(section_items) == 1`. |

---

### BUG-020 (P3-A)
| Field | Value |
|---|---|
| **ID** | BUG-020 |
| **Title** | Multiple Events not grouped under shared heading |
| **Status** | Open |
| **Area** | `ChucksEvents/events/compile_events.py` |
| **Symptom** | Event rows that share a title or lead image in the "Hosts with Multiple Events" section each render as independent items rather than being grouped under one heading. |
| **Cause / Fix** | No grouping logic in current compiler. Planned after BUG-017 is resolved. |

---

### BUG-021 (P3-B)
| Field | Value |
|---|---|
| **ID** | BUG-021 |
| **Title** | No rotation of same-date bulletin items within a section |
| **Status** | Deferred |
| **Area** | `ChucksBulletin/bulletins/compile_bulletin.py` |
| **Symptom** | Multiple bulletins in the same section with the same `Received` date always appear in CSV order. The same submitter is always last (or first) across issues. |
| **Cause / Fix** | No rotation logic. CSV-based rotation planned for current phase; replace with SQL query at database migration. Deferred until P1 items resolved. |

---

### BUG-022 (P3-C)
| Field | Value |
|---|---|
| **ID** | BUG-022 |
| **Title** | No `NEW` badge on first-appearance bulletin items |
| **Status** | Deferred |
| **Area** | `ChucksBulletin/bulletins/compile_bulletin.py` |
| **Symptom** | Items appearing in their first issue are not visually distinguished from returning items. |
| **Cause / Fix** | No prior-issue comparison logic. Plan: compare current intermediate CSV against prior issue's intermediate CSV (stored in `System/` with issue-date filenames). CSV-diff for current phase; replace with SQL at migration. Deferred until P1 items resolved. |

---

*Chuck's List Builder — Bug Ledger*
*Append new entries at the bottom of the appropriate section. Never delete resolved entries.*
# Chuck's List Builder — Operator Guide

> This is your complete reference for running the pipeline day-to-day.
> Read this before asking a developer for help — most answers are here.
>
> For technical architecture and bug history, see [ENGINEER_GUIDE.md](ENGINEER_GUIDE.md).
> For the active bug ledger, see [BUG_LIST.md](BUG_LIST.md).

***

## Table of Contents

- [What This Pipeline Does](#what-this-pipeline-does)
- [Directory Tree](#directory-tree)
- [File Roles](#file-roles)
- [Pre-Run Checklist](#pre-run-checklist)
- [CLI Quick Reference](#cli-quick-reference)
- [CSV Column Contracts](#csv-column-contracts)
- [Running the Build](#running-the-build)
- [Reading the Output](#reading-the-output)
- [Error Message Reference](#error-message-reference)
- [Uploading to Zoho Campaigns](#uploading-to-zoho-campaigns)
- [Roadmap](#roadmap)
- [Guiding Principles](#guiding-principles)

***

## What This Pipeline Does

Staff maintain a master spreadsheet of submitted items in Google Drive.
On publication day they export two CSV files and run one command.
The builder reads those exports and produces two complete, ready-to-send
HTML email files:

| Edition | What it contains | Output file |
|---|---|---|
| **Bulletin** | Housing, swap market, services, community announcements | `chucks_bulletin_final_output.html` |
| **Events** | Upcoming community events, sorted by type | `chucks_events_final_output.html` |

Both files are formatted for elderly and low-vision readers — large text,
high contrast, accessible links — and are safe for direct upload to
Zoho Campaigns.

***

## Directory Tree

```
ChucksList_Builder/
├── Chucks_List_Builder.py              Entry point — runs both pipelines
│
├── ChucksBulletin/                     Bulletin pipeline + Zoho staging folder
│   ├── bulletins/
│   │   ├── preprocess_bulletin_text.py     Stage 1: validate + date-filter
│   │   ├── compile_bulletin.py             Stage 2: render HTML
│   │   ├── Bulletins.csv                   Raw source export (not committed)
│   │   └── bulletins_data.csv              Intermediate CSV (not committed)
│   ├── Images/                         Local images — never committed to git
│   └── chucks_bulletin_final_output.html   Final output (not committed)
│
├── ChucksEvents/                       Events pipeline + Zoho staging folder
│   ├── events/
│   │   ├── preprocess_events_text.py       Stage 1: validate + date-filter
│   │   ├── compile_events.py               Stage 2: render HTML
│   │   ├── Events.csv                      Raw source export (not committed)
│   │   └── events_data.csv                 Intermediate CSV (not committed)
│   ├── Images/                         Local images — never committed to git
│   └── chucks_events_final_output.html     Final output (not committed)
│
└── System/
    ├── SYSTEM_README.md                This file — operator guide
    ├── ENGINEER_GUIDE.md               Developer reference
    ├── BUG_LIST.md                     Bug ledger
    ├── SEED_PROMPT.md                  AI agent operating instructions
    └── config.py.template.py           Config template (config.py is git-ignored)
```

**Files never committed to git:**
`Bulletins.csv`, `Events.csv`, `bulletins_data.csv`, `events_data.csv`,
`chucks_bulletin_final_output.html`, `chucks_events_final_output.html`,
all contents of `Images/`, `config.py`, `System/logs/`

***

## File Roles

| File | What it does |
|---|---|
| `Chucks_List_Builder.py` | Orchestrates both pipelines with one command. Calls preprocess then compile for each edition. Emits `[REMIND]` callout prompts if flags are omitted. |
| `preprocess_bulletin_text.py` | Reads `Bulletins.csv`, validates fields, normalizes Markdown links, date-filters rows against `--issue-date`, writes `bulletins_data.csv`. |
| `compile_bulletin.py` | Reads `bulletins_data.csv`, renders full HTML email, writes `chucks_bulletin_final_output.html`. |
| `preprocess_events_text.py` | Reads `Events.csv`, validates fields, normalizes Markdown links, date-filters rows against `--issue-date`, writes `events_data.csv`. |
| `compile_events.py` | Reads `events_data.csv`, renders full HTML email, writes `chucks_events_final_output.html`. |
| `System/SYSTEM_README.md` | This file. |
| `System/ENGINEER_GUIDE.md` | Architecture decisions, non-obvious behaviors, migration path. Read before modifying any script. |
| `System/BUG_LIST.md` | Append-only bug ledger. Every known bug has an entry here. |
| `System/SEED_PROMPT.md` | Instructions for the AI coding agent. Update when project scope changes. |

***

## Pre-Run Checklist

Complete every item before running the build.

**CSV files**
- [ ] Export `Bulletins.csv` from Google Drive → place in `ChucksBulletin/bulletins/`
- [ ] Export `Events.csv` from Google Drive → place in `ChucksEvents/events/`
- [ ] Confirm both files are UTF-8, comma-delimited (not semicolons, not tabs)
- [ ] Confirm dates are in one of the accepted formats: `YYYY-MM-DD`, `M/D/YY`, or `M/D/YYYY`

**Images**
- [ ] All images referenced in the CSVs are present in `ChucksBulletin/Images/` or `ChucksEvents/Images/`
- [ ] Image filenames in CSVs use forward slashes: `Images/photo.jpg` (not backslash)
- [ ] Multi-image cells use pipe separation: `Images/a.jpg|Images/b.jpg` (max 3 images per item)

**Issue date**
- [ ] Confirm the `--issue-date` you plan to use — this controls which rows are included
- [ ] Bulletins: `Received <= issue_date <= Expires`
- [ ] Events: `Starts <= issue_date <= Expires`

**Callouts (optional but reviewed every issue)**
- [ ] Decide if you want custom callout text at the top of each email
- [ ] If yes, prepare your `--callout` and `--bottom-callout` text now
- [ ] If no, the pipeline will print `[REMIND]` messages showing the default text — review them

***

## CLI Quick Reference

### CLI Flags

| Flag | Required | Default | Description |
|---|---|---|---|
| `--issue-date YYYY-MM-DD` | ✅ Yes | — | Publication date for this issue |
| `--issue-type bulletin\|events\|both` | No | `both` | Run bulletin only, events only, or both pipelines |
| `--callout "TEXT"` | No | — | Top callout text; skips the interactive wizard if provided |
| `--bottom-callout "TEXT"` | No | — | Bottom callout text; **only honored when `--callout` is also set** |
| `--debug` | No | off | Enable verbose debug logging to stdout |
| `--log-to-file` | No | off | Write a timestamped build log to `System/logs/` |
| `--no-open-vscode` | No | off | Skip auto-opening VS Code and HTML files after build |

### Basic build — both editions

```bash
py Chucks_List_Builder.py --issue-date 2026-06-07
```

### Build with custom callout boxes

```bash
py Chucks_List_Builder.py --issue-date 2026-06-07 \
  --callout "Summer hours: office closed July 4th." \
  --bottom-callout "Next issue: July 12th."
```

### Build one edition only

```bash
py Chucks_List_Builder.py --issue-date 2026-06-07 --issue-type bulletin
py Chucks_List_Builder.py --issue-date 2026-06-07 --issue-type events
```

### Suppress VS Code auto-open

```bash
py Chucks_List_Builder.py --issue-date 2026-06-07 --no-open-vscode
```

### Write a timestamped log file

```bash
py Chucks_List_Builder.py --issue-date 2026-06-07 --log-to-file
```
Log is written to `System/logs/build_YYYYMMDD_HHMMSS.log` (git-ignored).

### Debug mode — verbose output

```bash
py Chucks_List_Builder.py --issue-date 2026-06-07 --debug
```

### All flags

| Flag | Required | Default | Purpose |
|---|---|---|---|
| `--issue-date YYYY-MM-DD` | **Yes** | none | Controls row inclusion for both editions |
| `--issue-type bulletin\|events\|both` | No | `both` | Run bulletin only, events only, or both pipelines |
| `--callout "text"` | No | Default text | Top callout box text in both emails |
| `--bottom-callout "text"` | No | Default text | Bottom callout box text in both emails |
| `--bulletin` | No | off | Run bulletin pipeline only |
| `--events` | No | off | Run events pipeline only |
| `--no-open-vscode` | No | off | Suppress VS Code auto-open of output HTML |
| `--log-to-file` | No | off | Write timestamped log to `System/logs/` |
| `--debug` | No | off | Verbose diagnostic output |

***

## CSV Column Contracts

### Bulletins.csv

| Column | Required | Format | Notes |
|---|---|---|---|
| `Title` | Yes | Plain text | Shown as item heading |
| `Body` | Yes | Plain text or Markdown links `[label](url)` | Bare URLs auto-linked |
| `Section` | Yes | See valid values below | Controls grouping and sort order |
| `Received` | Yes | `YYYY-MM-DD`, `M/D/YY`, or `M/D/YYYY` | Row included if `Received <= issue_date` |
| `Expires` | Yes | Same date formats | Row included if `Expires >= issue_date` |
| `Image` | No | `Images/filename.jpg` or pipe-separated list | Max 3 images; prepend `Images/` if missing (warns) |
| `Contact` | No | Plain text, email, or `[label](url)` | Rendered below body |
| `Price` | No | Plain text | Rendered as a label if present |
| `notes` | No | Any | Staff-only annotation — never rendered, never written to intermediate CSV |

**Valid Section values (Bulletins):**
- `Urgent Bulletins` — always rendered first regardless of item count
- `Housing Opportunities`
- `Swap Market`
- `Local Services & Help`
- `Community Announcements`

Non-Urgent sections are sorted by ascending item count after Urgent.

### Events.csv

| Column | Required | Format | Notes |
|---|---|---|---|
| `Title` | Yes | Plain text | Shown as item heading |
| `Body` | Yes | Plain text or Markdown links `[label](url)` | Bare URLs auto-linked |
| `Section` | Yes | See valid values below | Controls grouping |
| `Starts` | Yes | `YYYY-MM-DD`, `M/D/YY`, or `M/D/YYYY` | Row included if `Starts <= issue_date` |
| `Expires` | Yes | Same date formats | Row included if `Expires >= issue_date`; maps to `Ends` in intermediate CSV |
| `Image` | No | Same as Bulletins | Max 3 images |
| `Contact` | No | Plain text, email, or `[label](url)` | Rendered below body |
| `notes` | No | Any | Staff-only annotation — never rendered |

**Valid Section values (Events):**
- `Single Events`
- `Hosts with Multiple Events`
- `Recurring Events`

### Markdown link format

Both CSVs support Markdown-style links anywhere in `Body` or `Contact`:

```
[label](https://example.com)
[here](https://example.com)
[email Chuck](mailto:chuck@example.com)
```

Bare URLs (no label) are auto-linked by the compiler. Mixed content
(text + links in the same cell) is supported.

### Date format examples

| Format | Example | Parser |
|---|---|---|
| ISO | `2026-06-07` | `DATE_RE_ISO` |
| Short | `6/7/26` | `DATE_RE_SHORT` |
| Long (LibreOffice default) | `6/7/2026` | `DATE_RE_LONG` |

All three formats are accepted in every date column in both CSVs.
LibreOffice Calc exports `M/D/YYYY` by default — this is fully supported.

***

## Running the Build

### What happens when you run the command

1. Builder emits `[REMIND]` lines if `--callout` flags are omitted (showing default text).
2. Preprocess runs for Bulletins: reads CSV, validates, date-filters, writes `bulletins_data.csv`.
3. Compile runs for Bulletins: reads intermediate CSV, renders HTML, writes output file.
4. Same two stages run for Events.
5. If VS Code is available and `--no-open-vscode` is not set, both HTML files open automatically.
6. Exit 0 = success. Exit non-zero = a stage failed; check output for `[ERROR]` tags.

### Zero-item output is a hard failure

If preprocess passes 0 rows and skips more than 0, it exits non-zero.
The build stops. You will see `[WARN]` lines explaining which rows were
skipped and why (bad date format, expired, out-of-window).
Fix the CSV and re-run. Do not proceed with a blank-issue HTML.

***

## Reading the Output

The CLI uses four tagged message types:

| Tag | Meaning | Action required |
|---|---|---|
| `[REMIND]` | A per-issue customization was not set; default used | Review the default text; add the flag if needed |
| `[WARN]` | A row was skipped or a field was auto-corrected | Review the flagged row; fix if unintentional |
| `[ERROR]` | Blocking failure; pipeline stopped | Fix the listed problem and re-run |
| `[AUTO-FIX]` | A safe correction was applied automatically | Review if desired; no action required |

### Common [WARN] messages

| Message | Cause | Fix |
|---|---|---|
| `Date format not recognized: "..."` | Date cell is empty or uses an unsupported format | Use `YYYY-MM-DD`, `M/D/YY`, or `M/D/YYYY` |
| `Row skipped — outside issue window` | `Received`/`Starts` after issue date, or `Expires` before issue date | Check the dates; adjust if the item should appear |
| `Image path missing "Images/" prefix — auto-corrected` | Image filename entered without folder prefix | Confirm the image file exists in the `Images/` folder |
| `More than 3 images in Image field — 4th entry dropped` | Four or more pipe-separated images in one cell | Move extra images to a link in the Body column |

### Common [ERROR] messages

| Message | Cause | Fix |
|---|---|---|
| `--issue-date is required` | Flag was omitted from the command | Add `--issue-date YYYY-MM-DD` |
| `Bulletins.csv not found` | CSV not placed in the correct folder | Place file at `ChucksBulletin/bulletins/Bulletins.csv` |
| `Events.csv not found` | CSV not placed in the correct folder | Place file at `ChucksEvents/events/Events.csv` |
| `0 rows passed; N rows skipped` | All rows filtered out | Check dates — most likely the issue date is outside all row windows |
| `Markdown link validation failed` | Malformed `[label](url)` in Body or Contact | Find the row listed in the error; fix the link syntax |

***

## Uploading to Zoho Campaigns

After a successful build:

1. Open `ChucksBulletin/chucks_bulletin_final_output.html` in a browser.
   Visually confirm it looks correct — items, images, callout boxes, TOC.
2. Open `ChucksEvents/chucks_events_final_output.html` and do the same.
3. Log into Zoho Campaigns.
4. Create or open the campaign for this issue.
5. Upload the HTML file using the "Import HTML" option.
6. Send a test to yourself first. Confirm images load and links work.
7. Send to the full list.

**Image note:** Images are referenced by relative path in the HTML.
They must be present in the staging folder (`ChucksBulletin/` or
`ChucksEvents/`) at send time, or uploaded to Zoho's media library
separately. The HTML output does not embed images — it links to them.

***

## Future Guide

### Pipeline Roadmap

| Phase | Status | Description |
|---|---|---|
| **Phase 1 — Local CLI** | ✅ Current production | Operator runs `py Chucks_List_Builder.py` on Windows. Output HTML uploaded manually to Zoho Campaigns. |
| **Phase 2 — cPanel Migration** | 🔜 Near-term | Move the existing CLI pipeline to a cPanel server. Behavior stays identical to Phase 1; removes local machine dependency. |
| **Phase 3 — Web GUI** | 📅 Medium/long-term | Browser-based interface at `mcafeefarm.biz` / `ChucksList.info`. Python + SQL backend. Any staff member can publish an issue without a terminal. |

**The local CLI is production until Phase 2 is tested and verified equivalent.**

### Phase 1 — Local CLI (current / production)

The pipeline runs on a local Windows machine. One command produces both HTML
emails. This is production until Phase 2 is tested and proven equivalent.

| Stage | Goal | Status |
|---|---|---|
| 1 | Document and stabilize current scripts | ✅ Complete |
| 2 | Harden both preprocessors to parity | ✅ Complete |
| 3 | Fix log path and cross-validation paths (BUG-023, BUG-024) | 🔄 In Progress |
| 4 | Fix nested output folder + duplicate files (BUG-017) | ⬜ Planned |
| 5 | VS Code file-open fix, callout newline, [REMIND] verify (BUG-030, BUG-029, BUG-025) | ⬜ Planned |
| 6 | Markdown auto-correct, TOC cleanup, section sort (BUG-026, BUG-019, BUG-018) | ⬜ Planned |
| 7 | TOC visual hierarchy, multiple events grouping, rotation, NEW badge (BUG-020–BUG-022) | ⬜ Deferred post-migration |

### Phase 2 — cPanel Server Migration (near term)

Migrate the existing CLI pipeline to a cPanel-hosted environment
(mcafeefarm.biz and/or ChucksList.info) so the build can run from a
server rather than a local Windows machine.

**Goal:** Same pipeline behavior, new hosting environment. No new features.

**Key migration work (tracked in ENGINEER_GUIDE.md):**
- Identify all Windows-specific assumptions in the current scripts
- Replace `py` with `python3` in any server-facing invocations
- Verify path anchoring works on Linux filesystem layout
- Confirm Python version compatibility on cPanel host
- Remove or gate the `--no-open-vscode` / VS Code auto-open behavior
- Test full build against real CSVs in the cPanel environment
- Document all configuration differences in ENGINEER_GUIDE.md

### Phase 3 — Web GUI (long term)

Build a staff-facing web interface on mcafeefarm.biz and/or ChucksList.info.
Staff log in, manage submissions, and generate email editions without
touching a CSV or command line.

- Python + SQL backend
- Database replaces CSV as the data store
- Email HTML generated from database queries
- CSV pipeline retired when server version is proven stable
- Timeline: several months out

## The Network Integration (Future Layer)

Chuck's List is one of the founding use cases for **The Network** — an open,
decentralized platform for community coordination built on AT Protocol,
Arweave, and modular governance contracts.

This pipeline will not change in Phase 2 or Phase 3 to accommodate The
Network. When Network integration is introduced, it layers on top of the
existing pipeline — it does not replace any part of it.

### What The Network will add

| Capability | What it means for Chuck's List |
|---|---|
| **Signed submission records** | Each bulletin or event submission becomes a signed ATProto record in a contributor's personal data repository — cryptographically tied to the submitter, portable, and independently verifiable |
| **Tamper-evident archive** | Final compiled editions are hashed and anchored to Arweave, creating a permanent, immutable record of every issue — no issue can be silently edited after distribution |
| **Community trust layer** | Listings can carry reputation signals from the community (verified local business, trusted neighbor) without requiring a centralized moderation authority |
| **Web board (Phase 4+)** | The Phase 3 GUI naturally extends to a public-facing community board where listings live as browsable records — not just email — while the email pipeline continues alongside it |

### What does not change

- The CSV intake process and two-pipeline architecture remain unchanged
- Zoho Campaigns delivery is not replaced — The Network board runs alongside it
- Chuck McAfee's editorial control over what goes out is fully preserved
- No personal data from contributors is exposed or stored on The Network
  without explicit opt-in from the submitter

### Status

> **Not started.** The Network is in architectural definition. This section
> documents the intended integration path so it informs Phase 3 GUI design
> decisions — particularly around the submission form, the database schema,
> and the web output format.
>
> When The Network integration thread is opened, a link to the relevant
> spec will be added here.

***

## Guiding Principles

- **The local CLI is production.** Do not treat the cPanel or GUI versions as
  production until they are tested and confirmed equivalent. Document this
  status in every release note.

- **Blank issues are hard failures.** If the build produces 0 items, it
  exits non-zero. Never upload a blank-issue HTML to Zoho. Fix the CSV first.

- **The `notes` column is staff-only.** It is never rendered and never
  written to intermediate files. Use it freely for internal annotations.

- **Images are never committed to git.** Place them in `Images/` locally.
  Back them up separately. The repo contains only code and documentation.

- **One command, two editions.** The pipeline always produces both Bulletin
  and Events outputs in a single run unless you explicitly use
  `--bulletin` or `--events`.

### Keeping the README Current

After any session that closes a bug or advances a goal, update these three
sections of `README.md` before committing:

1. **Active Goals** — reflect the new active goal and adjust the staged queue.
2. **Recent Fixes** — prepend the newly fixed bug; remove the oldest if the
   table exceeds 10 rows.
3. **Current Pipeline Status** — change the status emoji for any bug that moved.

This takes less than two minutes and keeps the repo front page accurate for
anyone who lands there cold.

***

*Chuck's List Builder — Operator Guide*
*For technical internals, see ENGINEER_GUIDE.md.*
*For the bug ledger, see BUG_LIST.md.*
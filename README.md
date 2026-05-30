# README.md — Chuck's List Builder

```markdown
# Chuck's List Builder

A two-pipeline, CSV-to-HTML community newsletter publishing system for 
**Chuck's List** — serving Montezuma County, Colorado and surrounding 
communities including Cortez, Dolores, Mancos, Towaoc, Rico, Dove Creek, 
and Cahone.

The system transforms an editorial spreadsheet into accessible, 
email-safe HTML for delivery through Zoho Campaigns. It is intentionally 
boring, deterministic, and reliable. One command. Two pipelines. Clean HTML.

Long-term, it is the foundation for a database-backed, web-driven 
publishing platform on [mcafeefarm.biz](https://www.mcafeefarm.biz).

---

## Current System Status

> **Phase: Local Hardening**  
> The local CSV-to-HTML pipeline is the current production system.  
> Web platform and database migration come *after* this is stable.

---

## How It Works

```
Chucks-list-MASTER.ods
        │
        ├── export ──► Bulletins.csv
        │                   │
        │            preprocess_bulletin_text.py
        │                   │
        │            bulletins_data.csv (intermediate)
        │                   │
        │            compile_bulletin.py
        │                   │
        │            chucks_bulletin_final_output.html
        │
        └── export ──► Events.csv
                            │
                     preprocess_events_text.py
                            │
                     events_data.csv (intermediate)
                            │
                     compile_events.py
                            │
                     chucks_events_final_output.html
```

Both outputs are reviewed and uploaded to **Zoho Campaigns** for delivery.

---

## Repository Structure

```
ChucksList_Builder/
├── Chucks_List_Builder.py          # Canonical one-command orchestrator
├── config.py.template.py           # Local config template (copy → config.py)
├── .gitignore
├── README.md
│
├── bulletins/
│   ├── preprocess_bulletin_text.py         # Normalize, filter, validate bulletins
│   ├── compile_bulletin.py                 # Render bulletins to email-safe HTML
│   └── chucks-list-bulletin-template.html  # HTML template for bulletins
│
└── events/
    ├── preprocess_events_text.py           # Normalize, filter, validate events
    ├── compile_events.py                   # Render events to email-safe HTML
    └── chucks-list-event-template.html     # HTML template for events
```

> **Note:** CSV data files, output HTML, and images are local-only and  
> excluded from version control via `.gitignore`.

---

## Canonical Command

```bash
py Chucks_List_Builder.py --issue-date YYYY-MM-DD
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--issue-date YYYY-MM-DD` | *(required)* | Publication date for this issue |
| `--issue-type bulletin\|events\|both` | `both` | Which pipeline(s) to run |
| `--log-to-file` | off | Write build log to `logs/` |
| `--no-open-vscode` | off | Skip auto-opening output in VS Code |

### Examples

```bash
# Full run — both pipelines
py Chucks_List_Builder.py --issue-date 2026-06-07

# Bulletins only
py Chucks_List_Builder.py --issue-date 2026-06-07 --issue-type bulletin

# Events only, with log file
py Chucks_List_Builder.py --issue-date 2026-06-07 --issue-type events --log-to-file
```

---

## Local Setup

### Requirements

- Python 3.10+
- LibreOffice (for ODS → CSV export)
- VS Code (optional, for output preview)

### First-time setup

1. Clone this repository.
2. Copy `config.py.template.py` to `config.py` and fill in local paths.
3. Export `Bulletins.csv` and `Events.csv` from `Chucks-list-MASTER.ods`.
4. Place image files in your local `Images/` directory.
5. Run the canonical command above.

---

## Content Source

The editorial source is `Chucks-list-MASTER.ods`, maintained locally.

### Bulletins CSV fields

| Field | Description |
|---|---|
| `received` | Date entry was received |
| `expires` | Last issue date entry should appear |
| `Section` | Canonical section name (see below) |
| `Title` | Entry headline |
| `Text` | Body text — plain, paragraph-break-aware |
| `Image` | Optional image filename |
| `notes` | Internal notes — **ignored by automation** |

### Events CSV fields

| Field | Description |
|---|---|
| `starts` | First date event is active/relevant |
| `ends` | Last date event is active/relevant |
| `Title` | Event name |
| `Text` | Body text — plain, paragraph-break-aware |
| `Image` | Optional image filename |
| `notes` | Internal notes — **ignored by automation** |

---

## Pipeline Rules

### Bulletin inclusion rule

An entry is included when:

```
received <= issue_date <= expires
```

### Event inclusion rule

An event is included when:

```
starts <= issue_date <= ends
```

### Canonical bulletin section order

1. Urgent Bulletins
2. Housing Opportunities
3. Swap Market
4. Local Services & Help
5. Community Announcements

---

## Design Requirements

### Accessibility (non-negotiable)

Chuck's List serves elderly and low-vision readers. The HTML output must:

- Use large, readable text with generous line spacing
- Maintain strong color contrast throughout
- Use live text — important information must never be image-only
- Render clearly in email clients without JavaScript
- Use meaningful link text, not bare raw URLs

### Visual Identity

The color scheme reflects **Montezuma County / Mesa Verde, Colorado**:  
warm earth tones, canyon reds, desert sage, and sandstone neutrals —  
readable and dignified, not marketing-flashy.

### Images

- Included in email where present
- Clickable/openable in a new tab where appropriate
- Proper alt text required
- Path resolution must be consistent across both pipelines

### Text and formatting

- Paragraph breaks are defined by blank lines (`\n\n`) in source text
- List-like blocks (lines starting with `- `, `* `, `•`) render as `<ul><li>`
- Plain-text authoring is the model — no Markdown literacy required from staff
- Poster-supplied spacing and formatting must survive into rendered output

### Table of Contents

- Every section/entry has a deterministic anchor
- TOC links must land the reader at the **top** of the correct entry
- Duplicate titles must not cause anchor collisions

---

## CLI Behavior

The builder is designed to guide the operator, not just fail.

- Date format errors produce a clear fix instruction
- Missing scripts produce a path-specific error message
- Stage failures stop the pipeline immediately with the error surfaced
- A build summary lists every passed and failed stage
- Failed builds explicitly warn: **do not upload partial output to Zoho**

---

## Long-Term Goals

This repository is the foundation for a broader publishing platform:

### Website platform — [mcafeefarm.biz](https://www.mcafeefarm.biz)

- Move publishing workflow to the web
- Staff login and admin content management
- Approved subscriber submission forms
- Moderation and review workflow
- Website listings generated from database records
- Email editions generated from database records

### Database migration

- Store bulletins and events in a normalized database
- Support searchable bulletin boards, event calendars, and archives
- Preserve plain-text-first authoring in web forms
- Keep automation incremental with human validation at key steps

### Email automation

- Continue using Zoho Campaigns for delivery in the near term
- Evaluate direct-send alternatives when the web platform is stable
- Generate email editions from database records instead of CSV exports

---

## Guiding Principles

- **Boring beats clever.** Deterministic transforms over magic.
- **Plain text first.** Staff paste from email — the system adapts.
- **Explicit pipelines.** Bulletins and Events stay separate and documented.
- **Accessibility is core.** Not a polish pass — built in from the start.
- **One command.** The full local build runs from one CLI call.
- **Guide, don't just fail.** CLI output tells the operator what to fix.
- **Validate before redesigning.** Understand what exists before changing it.

---

## Staged Migration Roadmap

| Stage | Goal | Status |
|---|---|---|
| 1 | Document and stabilize current scripts | 🔄 In progress |
| 2 | Mirror CSV data into a database | ⬜ Planned |
| 3 | Build admin UI on mcafeefarm.biz | ⬜ Planned |
| 4 | Generate website listings from database | ⬜ Planned |
| 5 | Generate email editions from database | ⬜ Planned |
| 6 | Retire CSV dependence when safe | ⬜ Planned |

---

## Contributing / Engineering Notes

- Read existing scripts before proposing changes
- Do not assume current code is fully working — treat every engagement as a validation
- Validate against real CSV exports and real issue dates
- Prefer full-file replacements over speculative partial patches
- Label every file you touch with its role in the pipeline
- Write concise engineer-facing comments and docstrings
- Do not push complexity ahead of proven need

---

*Chuck's List Builder — Montezuma County community publishing.*  
*Reliable. Readable. One command.*
```

***
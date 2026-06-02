# Chuck's List Builder

**Chuck's List is a long-running community email list where Montezuma County neighbors share local events, housing, services, and other happenings.**

Started and run by local farmer and community member Chuck McAfee, the list has connected the Four Corners area for years — delivering announcements, swap offers, housing leads, event notices, and local news directly to subscribers' inboxes via Zoho Campaigns.

This repository is the production tooling that powers each issue.

***

## What This Repo Does

Staff maintain a master spreadsheet of submitted items. On publication day, they export two CSV files and run one command. This builder reads those exports and produces two complete, ready-to-send HTML emails:

| Edition | What it contains | Output file |
|---|---|---|
| **Bulletin** | Housing, swap market, services, community announcements | `chucks_bulletin_final_output.html` |
| **Events** | Upcoming community events, sorted by type | `chucks_events_final_output.html` |

Both emails are formatted for elderly and low-vision readers — large text, high contrast, accessible links — and are safe for upload directly to Zoho Campaigns.

***

## Who This Is For

| Person | What they need |
|---|---|
| **Staff / operators** | Read [System/SYSTEM_README.md](System/SYSTEM_README.md) — the complete operator guide |
| **Developers / engineers** | Read [System/ENGINEER_GUIDE.md](System/ENGINEER_GUIDE.md) — architecture, contracts, bug history |
| **Anyone reporting a bug** | See [System/BUG_LIST.md](System/BUG_LIST.md) for the active bug ledger |

***

## Quick Start

```bash
py Chucks_List_Builder.py --issue-date YYYY-MM-DD
```

Before running, place the two CSV exports from Google Drive:
- `Bulletins.csv` → `ChucksBulletin/bulletins/`
- `Events.csv` → `ChucksEvents/events/`

Full pre-run checklist and CLI flag reference: [System/SYSTEM_README.md](System/SYSTEM_README.md)

***

## Where This Is Headed

The pipeline currently runs locally on a Windows machine. The plan, in three phases:

**Phase 1 — Now (stable):**
Local CLI pipeline on Windows. One command produces both HTML emails. This is production.

**Phase 2 — Near term:**
Migrate the existing CLI pipeline to a cPanel server (mcafeefarm.biz / ChucksList.info) so the build can run from a hosted environment rather than a local machine. No new features — same pipeline, new home.

**Phase 3 — Long term:**
Web-based GUI on mcafeefarm.biz and/or ChucksList.info. Staff log in, enter submissions, and generate emails without touching a CSV or command line. Python + SQL backend. This is months out.

***

## Repository Layout

```
ChucksList_Builder/
├── Chucks_List_Builder.py          Entry point — runs both pipelines
├── ChucksBulletin/                 Bulletin pipeline + Zoho staging
│   ├── bulletins/
│   │   ├── preprocess_bulletin_text.py
│   │   ├── compile_bulletin.py
│   │   └── [generated files — not committed]
│   └── Images/                     Local only — never committed
├── ChucksEvents/                   Events pipeline + Zoho staging
│   ├── events/
│   │   ├── preprocess_events_text.py
│   │   ├── compile_events.py
│   │   └── [generated files — not committed]
│   └── Images/                     Local only — never committed
└── System/
    ├── SYSTEM_README.md            Operator guide
    ├── ENGINEER_GUIDE.md           Developer reference
    └── BUG_LIST.md                 Bug ledger
```

***

## Current Pipeline Status

| Area | Status |
|---|---|
| Bulletin pipeline | ✅ Stable |
| Events pipeline | ✅ Stable |
| Date parsing (all LibreOffice formats) | ✅ Fixed |
| Markdown link rendering | ✅ Fixed |
| Windows path safety | ✅ Fixed |
| Multi-image fields | ✅ Fixed |
| Nested output folders (BUG-017) | 🔄 In Progress |
| Section ordering by size (BUG-018) | 🔄 Planned |
| cPanel migration | ⬜ Next phase |
| Web GUI | ⬜ Long term |

For the full bug and punch list, see [System/BUG_LIST.md](System/BUG_LIST.md).

***

*Chuck's List — Montezuma County, Colorado.*
*Pipeline maintained by KuztomTech. Questions? See the operator guide or open an issue.* Update
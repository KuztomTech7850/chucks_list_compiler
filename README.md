# Chuck's List Builder

Chuck's List is a community publishing effort serving Montezuma County and
surrounding communities in southwestern Colorado. It distributes local
bulletins — housing leads, swap offers, services, announcements — and
community events to a subscriber list via Zoho Campaigns email.

This repository is the production pipeline that powers each issue. Staff work with the builder and get two complete HTML emails ready
to upload to Zoho.

***

## What This Repo Does

| Pipeline | Input | Output |
|---|---|---|
| Bulletin | `Bulletins.csv` exported from Google Drive | `chucks_bulletin_final_output.html` |
| Events | `Events.csv` exported from Google Drive | `chucks_events_final_output.html` |

Both pipelines are independent. Each runs a normalize/validate stage, then
a render stage, producing table-based HTML email safe for Zoho Campaigns
and accessible to elderly readers.

***

## Living Documents

| Document | Purpose | Last Updated |
|---|---|---|
| [System/SYSTEM_README.md](System/SYSTEM_README.md) | Operator guide — how to run the pipeline, CLI flags, CSV contracts, section ordering, error message reference | 2026-06-02 |
| [System/ENGINEER_GUIDE.md](System/ENGINEER_GUIDE.md) | Developer reference — architecture contracts, bug history, open punch list, what not to break | 2026-06-02 |

> Both documents must be updated as part of any commit that changes pipeline
> behavior, CLI flags, file locations, or data contracts. See the Engineer
> Guide for the update protocol.

***

## Current Status

| Area | Status | Notes |
|---|---|---|
| Both pipelines | ✅ Stable | Bulletin and Events produce clean HTML |
| Date parsing | ✅ Fixed | All three LibreOffice/ISO formats accepted |
| Markdown link rendering | ✅ Fixed | QUOTE_ALL and escape-then-linkify pipeline correct |
| Windows path safety | ✅ Fixed | All asset paths use forward-slash URL syntax |
| Multi-image fields | ✅ Fixed | Pipe-split before render, max 3 enforced |
| Nested output folders (P1-C) | 🔄 In progress | `ChucksBulletin/ChucksBulletin/` bug being resolved |
| TOC and section ordering (P2-A, P2-B) | 🔄 In progress | Sort by item count; single-item TOC suppression |
| Multiple Events grouping (P3-A) | ⬜ Planned | |
| Bulletin rotation / NEW badge (P3-B, P3-C) | ⬜ Planned | |
| Database backend | ⬜ Planned | End-state migration; current CSV foundation remains |

***

## Quick Start

```bash
py Chucks_List_Builder.py --issue-date YYYY-MM-DD
```

Full CLI reference and pre-run checklist: [System/SYSTEM_README.md](System/SYSTEM_README.md)

***

## Repo Layout

ChucksList_Builder/
├── Chucks_List_Builder.py        Entry point
├── ChucksBulletin/               Bulletin pipeline + Zoho staging
├── ChucksEvents/                 Events pipeline + Zoho staging
├── Images/                       Shared images (local only, never committed)
└── System/
    ├── SYSTEM_README.md          Operator guide (System/SYSTEM_README.md)
    ├── ENGINEER_GUIDE.md         Developer reference
    └── logs/                     Build logs (local only)

---
*Chuck's List Builder — Montezuma County, Colorado.*
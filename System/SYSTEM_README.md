# SYSTEM_README.md — Snippet: Migration Roadmap section

> INSERT THIS SECTION between "## Roadmap" and "## Guiding Principles"
> Replace the existing ## Roadmap table entirely with the content below.

***

## Roadmap

### Phase 1 — Local CLI (current / production)

The pipeline runs on a local Windows machine. One command produces both HTML
emails. This is production until Phase 2 is tested and proven equivalent.

| Stage | Goal | Status |
|---|---|---|
| 1 | Document and stabilize current scripts | ✅ Complete |
| 2 | Harden both preprocessors to parity | ✅ Complete |
| 3 | Fix nested output folder bug (BUG-017) | 🔄 In progress |
| 4 | TOC and section ordering (BUG-018, BUG-019) | ⬜ Planned |
| 5 | Multiple Events grouping, rotation, NEW badge (BUG-020, BUG-021, BUG-022) | ⬜ Planned |

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
- Document any configuration differences in ENGINEER_GUIDE.md

### Phase 3 — Web GUI (long term)

Build a staff-facing web interface on mcafeefarm.biz and/or ChucksList.info.
Staff log in, manage submissions, and generate email editions without
touching a CSV or command line.

- Python + SQL backend
- Database replaces CSV as the data store
- Email HTML generated from database queries
- CSV pipeline retired when server version is proven stable
- Timeline: several months out

Update
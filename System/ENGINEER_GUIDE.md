# ENGINEER_GUIDE.md — Two Snippets

***

## Snippet 1 — Remove artifact from line 1

DELETE the first two lines of the file:

  File 2 — System/ENGINEER_GUIDE.md (new)
  text

The file must open with:

  # Chuck's List Builder — Engineer Guide

***

## Snippet 2 — Add BUG_LIST.md to File Roles table

In the ## File Roles section, add one row to the table.

CURRENT table ends with:
| `System/config.py.template.py` | Template for local config (config.py itself is git-ignored) |
| `System/logs/` | Timestamped build logs written by `--log-to-file`; git-ignored |

REPLACE those last two rows with:
| `System/SYSTEM_README.md` | Operator guide — keep current after every significant change |
| `System/ENGINEER_GUIDE.md` | This file — technical almanac for developers |
| `System/BUG_LIST.md` | Canonical bug ledger — append new entries; never delete resolved ones |
| `System/config.py.template.py` | Template for local config (config.py itself is git-ignored) |
| `System/logs/` | Timestamped build logs written by `--log-to-file`; git-ignored |

(Note: SYSTEM_README.md and ENGINEER_GUIDE.md rows likely already exist
in your table — verify and deduplicate if so. The new row is BUG_LIST.md.) Update
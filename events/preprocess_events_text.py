"""
events/preprocess_events_text.py
Role: Read raw Events.csv, validate, filter by issue_date, write events_data.csv
Pipeline stage: PREPROCESS (runs before compile_events.py)
Called by: Chucks_List_Builder.py via subprocess
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJ_DIR   = SCRIPT_DIR.parent
INPUT_CSV  = PROJ_DIR / "Events.csv"
OUTPUT_CSV = SCRIPT_DIR / "events_data.csv"

REQUIRED_COLS = ["Title", "Body", "Starts", "Ends"]
OPTIONAL_COLS = ["Location", "Contact", "Phone", "Image"]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(val: str, row_num: int, field: str) -> date | None:
    val = val.strip()
    if not val:
        print(
            f"  [WARN] Row {row_num}: field '{field}' is empty. "
            f"Expected format: YYYY-MM-DD. Item will be skipped.",
            file=sys.stderr,
        )
        return None
    if not DATE_RE.match(val):
        print(
            f"  [WARN] Row {row_num}: field '{field}' has value '{val}'. "
            f"Expected YYYY-MM-DD. Item will be skipped.",
            file=sys.stderr,
        )
        return None
    try:
        return date.fromisoformat(val)
    except ValueError as e:
        print(
            f"  [WARN] Row {row_num}: field '{field}' value '{val}' is not a valid date: {e}. "
            f"Item will be skipped.",
            file=sys.stderr,
        )
        return None


def preprocess_events(issue_date_str: str) -> int:
    """
    Filter Events.csv by: starts <= issue_date <= ends.
    Write passing rows to events_data.csv.
    """
    try:
        issue_date = date.fromisoformat(issue_date_str)
    except ValueError:
        print(
            f"ERROR: --issue-date '{issue_date_str}' is not a valid date. "
            f"Expected YYYY-MM-DD.",
            file=sys.stderr,
        )
        return 1

    if not INPUT_CSV.exists():
        print(
            f"ERROR: Source file not found: {INPUT_CSV}\n"
            f"  Fix: Export the Events sheet from Chucks-list-MASTER.ods "
            f"as CSV to {INPUT_CSV}",
            file=sys.stderr,
        )
        return 1

    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print(
                    "ERROR: Events.csv appears empty or has no header row.\n"
                    "  Fix: Re-export from Chucks-list-MASTER.ods.",
                    file=sys.stderr,
                )
                return 1
            actual_cols = set(reader.fieldnames)
            missing = set(REQUIRED_COLS) - actual_cols
            if missing:
                print(
                    f"ERROR: Events.csv is missing required columns: "
                    f"{', '.join(sorted(missing))}\n"
                    f"  Found columns: {', '.join(sorted(actual_cols))}\n"
                    f"  Fix: Re-export from Chucks-list-MASTER.ods.",
                    file=sys.stderr,
                )
                return 1
            all_rows = list(reader)
    except UnicodeDecodeError:
        print(
            "ERROR: Events.csv could not be decoded as UTF-8.\n"
            "  Fix: Re-export with UTF-8 encoding.",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        print(f"ERROR reading {INPUT_CSV}: {e}", file=sys.stderr)
        return 1

    passing_rows = []
    skipped = 0

    for i, row in enumerate(all_rows, start=2):
        title  = (row.get("Title") or "").strip()
        starts_str = (row.get("Starts") or "").strip()
        ends_str   = (row.get("Ends") or "").strip()
        body   = (row.get("Body") or "").replace("\r\n", "\n").replace("\r", "\n")

        if not any(v.strip() for v in row.values()):
            continue

        if not title:
            print(
                f"  [WARN] Row {i}: Title is empty. "
                f"Body starts: '{body[:40]}'. Item skipped.",
                file=sys.stderr,
            )
            skipped += 1
            continue

        starts = parse_date(starts_str, i, "Starts")
        ends   = parse_date(ends_str, i, "Ends")

        if starts is None or ends is None:
            skipped += 1
            continue

        # Inclusion rule: starts <= issue_date <= ends
        if not (starts <= issue_date <= ends):
            continue

        if starts > ends:
            print(
                f"  [WARN] Row {i}: Title='{title}' has Starts ({starts_str}) "
                f"after Ends ({ends_str}). Check the source workbook.",
                file=sys.stderr,
            )

        body_lower = body.lower()
        if "href=" in body_lower or "<a " in body_lower:
            print(
                f"  [WARN] Row {i}: Title='{title}' Body contains raw HTML. "
                f"Use plain-text URLs only.",
                file=sys.stderr,
            )

        out_row = {col: (row.get(col) or "").strip() for col in REQUIRED_COLS + OPTIONAL_COLS}
        out_row["Body"] = body
        passing_rows.append(out_row)

    out_cols = REQUIRED_COLS + OPTIONAL_COLS
    try:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(passing_rows)
    except Exception as e:
        print(f"ERROR writing {OUTPUT_CSV}: {e}", file=sys.stderr)
        return 1

    print(
        f"  [OK] Events preprocess: "
        f"{len(passing_rows)} items written to {OUTPUT_CSV} "
        f"({skipped} skipped, issue_date={issue_date_str})"
    )
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Preprocess Events.csv.")
    p.add_argument("--issue-date", required=True, help="Issue date YYYY-MM-DD")
    args = p.parse_args()
    sys.exit(preprocess_events(args.issue_date))
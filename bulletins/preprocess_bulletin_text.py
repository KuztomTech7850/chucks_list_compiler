"""
bulletins/preprocess_bulletin_text.py
Role: Read raw Bulletins.csv, validate, filter by issue_date, write bulletins_data.csv
Pipeline stage: PREPROCESS (runs before compile_bulletin.py)
Called by: Chucks_List_Builder.py via subprocess

Operator error messages include: row number, field name, raw value, expected fix.
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJ_DIR   = SCRIPT_DIR.parent
INPUT_CSV  = PROJ_DIR / "Bulletins.csv"
OUTPUT_CSV = SCRIPT_DIR / "bulletins_data.csv"

REQUIRED_COLS = ["Title", "Body", "Section", "Received", "Expires"]
OPTIONAL_COLS = ["Contact", "Phone", "Image"]

SECTION_ORDER = [
    "Urgent Bulletins",
    "Housing Opportunities",
    "Swap Market",
    "Local Services & Help",
    "Community Announcements",
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(val: str, row_num: int, field: str) -> date | None:
    """Parse YYYY-MM-DD string. Print actionable error and return None on failure."""
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
            f"  [WARN] Row {row_num}: field '{field}' has invalid date value '{val}'. "
            f"Expected format: YYYY-MM-DD (e.g., 2026-06-01). Item will be skipped.",
            file=sys.stderr,
        )
        return None
    try:
        return date.fromisoformat(val)
    except ValueError as e:
        print(
            f"  [WARN] Row {row_num}: field '{field}' date '{val}' is not a real date: {e}. "
            f"Item will be skipped.",
            file=sys.stderr,
        )
        return None


def normalize_text(text: str) -> str:
    """Normalize line endings. Do not strip intentional whitespace."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def preprocess_bulletins(issue_date_str: str) -> int:
    """
    Filter Bulletins.csv by: Received <= issue_date <= Expires.
    Write passing rows to bulletins_data.csv.
    Returns 0 on success, 1 on fatal error.
    """
    try:
        issue_date = date.fromisoformat(issue_date_str)
    except ValueError:
        print(
            f"ERROR: --issue-date '{issue_date_str}' is not a valid date. "
            f"Expected format: YYYY-MM-DD.",
            file=sys.stderr,
        )
        return 1

    if not INPUT_CSV.exists():
        print(
            f"ERROR: Source file not found: {INPUT_CSV}\n"
            f"  Fix: Export the Bulletins sheet from Chucks-list-MASTER.ods "
            f"as CSV (UTF-8, comma-delimited) to {INPUT_CSV}",
            file=sys.stderr,
        )
        return 1

    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print(
                    f"ERROR: {INPUT_CSV} appears empty or has no header row.\n"
                    f"  Fix: Re-export from Chucks-list-MASTER.ods.",
                    file=sys.stderr,
                )
                return 1
            actual_cols = set(reader.fieldnames)
            missing = set(REQUIRED_COLS) - actual_cols
            if missing:
                print(
                    f"ERROR: {INPUT_CSV} is missing required columns: "
                    f"{', '.join(sorted(missing))}\n"
                    f"  Found columns: {', '.join(sorted(actual_cols))}\n"
                    f"  Fix: Re-export from Chucks-list-MASTER.ods with all required columns.",
                    file=sys.stderr,
                )
                return 1

            all_rows = list(reader)

    except UnicodeDecodeError:
        print(
            f"ERROR: {INPUT_CSV} could not be decoded as UTF-8.\n"
            f"  Fix: Re-save/export the file with UTF-8 encoding.",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        print(f"ERROR reading {INPUT_CSV}: {e}", file=sys.stderr)
        return 1

    passing_rows = []
    skipped = 0

    for i, row in enumerate(all_rows, start=2):
        title    = (row.get("Title") or "").strip()
        received_str = (row.get("Received") or "").strip()
        expires_str  = (row.get("Expires") or "").strip()
        section  = (row.get("Section") or "").strip()
        body     = normalize_text(row.get("Body") or "")

        # Skip completely blank rows
        if not any(v.strip() for v in row.values()):
            continue

        if not title:
            print(
                f"  [WARN] Row {i}: Title is empty. "
                f"Section='{section}', Body starts with: '{body[:40]}'. "
                f"Item skipped — please add a Title in the source workbook.",
                file=sys.stderr,
            )
            skipped += 1
            continue

        received = parse_date(received_str, i, "Received")
        expires  = parse_date(expires_str, i, "Expires")

        if received is None or expires is None:
            skipped += 1
            continue

        # Date filter: Received <= issue_date <= Expires
        if not (received <= issue_date <= expires):
            continue  # normal exclusion, not an error

        if section and section not in SECTION_ORDER:
            print(
                f"  [WARN] Row {i}: Title='{title}', Section='{section}' is not "
                f"a recognized section name.\n"
                f"  Valid sections: {', '.join(SECTION_ORDER)}.\n"
                f"  Fix: Update the Section field in Chucks-list-MASTER.ods.",
                file=sys.stderr,
            )
            skipped += 1
            continue

        # Check for suspicious raw link text that may break Zoho
        body_lower = body.lower()
        if "href=" in body_lower or "<a " in body_lower:
            print(
                f"  [WARN] Row {i}: Title='{title}' Body appears to contain raw HTML "
                f"(<a> or href=). This may break Zoho import. "
                f"Fix: Use plain-text URLs in the Body field, not HTML.",
                file=sys.stderr,
            )

        out_row = {col: (row.get(col) or "").strip() for col in REQUIRED_COLS + OPTIONAL_COLS}
        out_row["Body"] = body  # use normalized body
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
        f"  [OK] Bulletins preprocess: "
        f"{len(passing_rows)} items written to {OUTPUT_CSV} "
        f"({skipped} skipped, issue_date={issue_date_str})"
    )
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Preprocess Bulletins.csv.")
    p.add_argument("--issue-date", required=True, help="Issue date YYYY-MM-DD")
    args = p.parse_args()
    sys.exit(preprocess_bulletins(args.issue_date))
"""
Chucks_List_Builder.py
Role: Single orchestration entrypoint for the Chuck's List publishing pipeline.
Called by operator with: py Chucks_List_Builder.py --issue-date YYYY-MM-DD

Flags:
  --issue-date YYYY-MM-DD        (required)
  --issue-type bulletin|events|both  (default: both)
  --callout TEXT                 Top callout text (skips wizard if provided)
  --bottom-callout TEXT          Bottom callout (only honored when --callout is also set)
  --debug                        Enable debug logging
  --log-to-file                  Write build log to logs/build_YYYY-MM-DD_HHMMSS.log
  --no-open-vscode               Skip opening VS Code after build

Interactive features:
  - Callout wizard:      prompts operator before pipeline runs if --callout not passed
  - Error panels:        failed stages display a formatted, scannable error block
  - Retry loop:          operator can fix errors and re-run the failed stage in place
  - CSV→HTML validation: after each compile, cross-checks the intermediate CSV
                         against the final HTML and reports any title/item discrepancies
  - HTML diff (optional): compares new HTML structure against previous run snapshot;
                          see ENABLE_HTML_DIFF below to toggle on/off

CHANGELOG
  2026-05-31  Bug 1 fix: emit [REMIND] when callout args not supplied.
              Wire --callout / --bottom-callout to compiler subprocesses.
  2026-06-01  Interactive CLI rewrite:
              - Callout wizard replaces [REMIND] nagging
              - Formatted error panels with [ERROR]/[WARN]/[AUTO-FIX] columns
              - Retry loop: failed stages re-run after operator fixes source
              - CSV→HTML cross-validation: checks intermediate CSV titles against
                rendered HTML item titles; surfaces any items dropped or phantom
                items that appear in HTML but have no CSV source row
              - HTML diff (disabled by default): structural comparison of new HTML
                vs previous output snapshot; toggle ENABLE_HTML_DIFF = True to
                activate. Wrapped in commented blocks for easy removal.
              - VS Code open targets the entire ChucksList_Builder folder +
                the two final HTML files
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

PROJ_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Feature flag — HTML diff against previous run snapshot
#
# Set to True to enable. When False, the snapshot logic is fully skipped.
# To remove this feature entirely, delete every block marked:
#   <!-- DIFF_VALIDATION_ENABLED --> ... <!-- /DIFF_VALIDATION_ENABLED -->
# ---------------------------------------------------------------------------
ENABLE_HTML_DIFF = False  # <!-- DIFF_VALIDATION_ENABLED -->

# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------

PIPELINE_STAGES = {
    "bulletin": [
        {
            "name": "Bulletin Preprocess",
            "script": PROJ_DIR / "bulletins" / "preprocess_bulletin_text.py",
            "pass_callout": False,
        },
        {
            "name": "Bulletin Compile",
            "script": PROJ_DIR / "bulletins" / "compile_bulletin.py",
            "pass_callout": True,
        },
    ],
    "events": [
        {
            "name": "Events Preprocess",
            "script": PROJ_DIR / "events" / "preprocess_events_text.py",
            "pass_callout": False,
        },
        {
            "name": "Events Compile",
            "script": PROJ_DIR / "events" / "compile_events.py",
            "pass_callout": True,
        },
    ],
}

# Intermediate CSV produced by each preprocess stage
INTERMEDIATE_CSV = {
    "bulletin": PROJ_DIR / "bulletins" / "bulletins_data.csv",
    "events":   PROJ_DIR / "events"    / "events_data.csv",
}

# Final HTML produced by each compile stage
OUTPUT_FILES = {
    "bulletin": PROJ_DIR / "bulletins" / "chucks_bulletin_final_output.html",
    "events":   PROJ_DIR / "events"    / "chucks_events_final_output.html",
}

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

DIVIDER       = "─" * 64
THICK_DIVIDER = "═" * 64

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_to_file: bool, issue_date: str) -> logging.Logger:
    logger = logging.getLogger("chucks_builder")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_to_file:
        logs_dir = PROJ_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        log_file = logs_dir / f"build_{ts}.log"
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.info(f"Log file: {log_file}")

    return logger


def validate_issue_date(issue_date_str: str) -> date:
    try:
        return date.fromisoformat(issue_date_str)
    except ValueError:
        print(
            f"\nERROR: --issue-date '{issue_date_str}' is not a valid date.\n"
            f"  Expected format: YYYY-MM-DD  (e.g. 2026-05-31)\n",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Callout wizard
# ---------------------------------------------------------------------------

def _prompt(msg: str, valid: set[str] | None = None) -> str:
    """
    Print a prompt and read one line from stdin.
    Loops until the response is in `valid` (case-insensitive) if valid is set.
    Exits cleanly on EOF (Ctrl+Z / Ctrl+D).
    """
    while True:
        try:
            print(msg, end="", flush=True)
            answer = input().strip()
        except EOFError:
            print("\n\nBuilder interrupted. Exiting.")
            sys.exit(0)

        if valid is None:
            return answer
        if answer.lower() in valid:
            return answer.lower()

        choices = "/".join(sorted(valid))
        print(f"  Please enter one of: {choices}")


def callout_wizard(
    passed_callout: str | None,
    passed_bottom: str | None,
) -> tuple[str | None, str | None]:
    """
    Interactive callout wizard.

    Rules:
    - If --callout was passed on the CLI, skip the wizard entirely.
    - Bottom callout can only be changed when a top callout is also being set.
    - Returns (top_callout, bottom_callout); None = use compiler default.
    """
    if passed_callout is not None:
        return passed_callout, passed_bottom

    print()
    print(THICK_DIVIDER)
    print("  CALLOUT SETUP")
    print(THICK_DIVIDER)

    has_callout = _prompt("  Do you have a callout for today's issue? [y/n]: ", {"y", "n"})

    if has_callout == "n":
        print("  ✓ No callout — top callout box will be suppressed.")
        print()
        return None, None

    which = _prompt("  Top callout only, or set both top AND bottom? [t/b]: ", {"t", "b"})

    print()
    print("  Enter the TOP callout text (press Enter when done):")
    print(f"  {DIVIDER}")

    top_lines: list[str] = []
    blank_count = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "" and top_lines:
            blank_count += 1
            if blank_count >= 1:
                break
        else:
            blank_count = 0
            top_lines.append(line)

    top_callout = " ".join(top_lines).strip()
    if not top_callout:
        print("  No top callout entered — top callout box will be suppressed.")
        return None, None

    print(f"\n  ✓ Top callout: \"{top_callout[:80]}{'...' if len(top_callout) > 80 else ''}\"")

    bottom_callout: str | None = None

    if which == "b":
        print()
        print("  Enter the BOTTOM callout text (press Enter when done):")
        print(f"  {DIVIDER}")

        bottom_lines: list[str] = []
        blank_count = 0
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "" and bottom_lines:
                blank_count += 1
                if blank_count >= 1:
                    break
            else:
                blank_count = 0
                bottom_lines.append(line)

        bottom_callout = " ".join(bottom_lines).strip() or None
        if bottom_callout:
            print(f"\n  ✓ Bottom callout: \"{bottom_callout[:80]}{'...' if len(bottom_callout) > 80 else ''}\"")
        else:
            print("  No bottom callout entered — using compiler default.")

    print()
    return top_callout, bottom_callout


# ---------------------------------------------------------------------------
# Formatted error panel
# ---------------------------------------------------------------------------

_LEVEL_LABEL = {
    "ERROR":    "  ✗ [ERROR]   ",
    "WARN":     "  ⚠ [WARN]    ",
    "AUTO-FIX": "  ✔ [AUTO-FIX]",
    "OK":       "  ✓ [OK]      ",
    "OTHER":    "               ",
}


def _classify_line(line: str) -> str:
    upper = line.upper()
    if "[ERROR]" in upper or upper.strip().startswith("ERROR"):
        return "ERROR"
    if "[WARN]" in upper or upper.strip().startswith("WARN"):
        return "WARN"
    if "[AUTO-FIX]" in upper:
        return "AUTO-FIX"
    if "[OK]" in upper:
        return "OK"
    return "OTHER"


def print_error_panel(stage_name: str, rc: int, stdout: str, stderr: str) -> None:
    """
    Render a visually organized, column-aligned error panel for a failed stage.
    """
    print()
    print(THICK_DIVIDER)
    print(f"  ✗  STAGE FAILED: {stage_name}  (exit {rc})")
    print(THICK_DIVIDER)

    all_lines = []
    for raw in (stdout or "").splitlines():
        if raw.strip():
            all_lines.append(raw.strip())
    for raw in (stderr or "").splitlines():
        if raw.strip():
            all_lines.append(raw.strip())

    if not all_lines:
        print()
        print("  (No output captured from subprocess.)")
        print(THICK_DIVIDER)
        return

    print()
    print("  ERRORS & WARNINGS")
    print(f"  {DIVIDER}")

    error_count = warn_count = autofix_count = 0

    for line in all_lines:
        level = _classify_line(line)
        clean = re.sub(r"^\s*\[(ERROR|WARN|AUTO-FIX|OK|REMIND)\]\s*", "", line, flags=re.IGNORECASE).strip()
        clean = re.sub(r"^(ERROR|WARN):\s*", "", clean, flags=re.IGNORECASE).strip()

        if level == "ERROR":
            error_count += 1
            label = _LEVEL_LABEL["ERROR"]
        elif level == "WARN":
            warn_count += 1
            label = _LEVEL_LABEL["WARN"]
        elif level == "AUTO-FIX":
            autofix_count += 1
            label = _LEVEL_LABEL["AUTO-FIX"]
        elif level == "OK":
            label = _LEVEL_LABEL["OK"]
        else:
            label = "    ↳          " if clean.lower().startswith("fix:") else _LEVEL_LABEL["OTHER"]

        # Word-wrap at 64 chars
        words = clean.split()
        lines_out: list[str] = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > 64 and current:
                lines_out.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines_out.append(current)

        for j, part in enumerate(lines_out):
            print(f"{label if j == 0 else '               '}{part}")

    print()
    print(f"  {DIVIDER}")
    parts = []
    if error_count:
        parts.append(f"{error_count} error(s)")
    if warn_count:
        parts.append(f"{warn_count} warning(s)")
    if autofix_count:
        parts.append(f"{autofix_count} auto-fixed")
    summary = "  ·  ".join(parts) if parts else "No labeled messages"
    print(f"  {summary}  ·  Fix the source CSV then confirm below.")
    print(THICK_DIVIDER)
    print()


# ---------------------------------------------------------------------------
# CSV → HTML cross-validation  (the real data validation you asked for)
#
# After compile succeeds, this function reads the intermediate CSV (the
# output of preprocess) and the final HTML, then cross-checks that every
# title in the CSV appears in the HTML and that no phantom titles appear in
# the HTML without a CSV source row.
#
# Discrepancies are printed as a structured report. The build is NOT blocked
# by this check — it is informational, because the compiler may legitimately
# transform or truncate a title slightly (e.g. html.escape). Any item that
# is clearly present but looks different is flagged as a REVIEW, not an ERROR.
# ---------------------------------------------------------------------------

def _csv_titles(csv_path: Path, pipeline: str) -> list[str]:
    """Read the Title column from the intermediate CSV."""
    if not csv_path.exists():
        return []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [(row.get("Title") or "").strip() for row in reader if (row.get("Title") or "").strip()]
    except Exception:
        return []


def _html_titles(html_path: Path) -> list[str]:
    """
    Extract item titles from compiled HTML.
    Targets <div class="section-title"> ... </div> blocks — the canonical
    title element in both bulletin and events compilers.
    """
    if not html_path.exists():
        return []
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
        # Match the section-title div, capture inner text, strip HTML tags
        raw_matches = re.findall(
            r'class="section-title[^"]*"[^>]*>(.*?)</div>',
            text,
            re.DOTALL | re.IGNORECASE,
        )
        titles = []
        for match in raw_matches:
            # Strip any residual HTML tags and decode common entities
            clean = re.sub(r"<[^>]+>", "", match)
            clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"').strip()
            if clean:
                titles.append(clean)
        return titles
    except Exception:
        return []


def _normalize_for_compare(title: str) -> str:
    """
    Normalize a title for fuzzy comparison:
    lowercase, collapse whitespace, strip punctuation differences.
    This lets us match "Bob's Goats" == "Bob&#39;s Goats" == "bob's goats".
    """
    t = title.lower()
    t = t.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"')
    t = re.sub(r"\s+", " ", t).strip()
    return t


def validate_csv_vs_html(pipeline: str) -> None:
    """
    Cross-check intermediate CSV titles against rendered HTML titles.

    Prints a structured report of:
      ✓  Item counts match
      ✗  Items in CSV but not found in HTML  (possible compile drop)
      ⚠  Items in HTML but not in CSV        (possible phantom / header bleed)
      ℹ  Count mismatch with no missing titles (possible duplicate rendering)
    """
    csv_path  = INTERMEDIATE_CSV[pipeline]
    html_path = OUTPUT_FILES[pipeline]

    csv_titles  = _csv_titles(csv_path, pipeline)
    html_titles = _html_titles(html_path)

    if not csv_titles and not html_titles:
        print(f"  [VALIDATION] No data to compare for {pipeline.upper()} — both CSV and HTML are empty or missing.")
        return

    print()
    print(f"  {DIVIDER}")
    print(f"  CSV → HTML VALIDATION  ({pipeline.upper()})")
    print(f"  {DIVIDER}")
    print(f"  CSV rows (preprocess output) : {len(csv_titles)}")
    print(f"  HTML items (compile output)  : {len(html_titles)}")

    # Build normalized lookup sets
    csv_norm  = {_normalize_for_compare(t): t for t in csv_titles}
    html_norm = {_normalize_for_compare(t): t for t in html_titles}

    csv_keys  = set(csv_norm.keys())
    html_keys = set(html_norm.keys())

    missing_from_html = csv_keys - html_keys    # in CSV but not rendered
    phantom_in_html   = html_keys - csv_keys    # in HTML but no CSV source

    if not missing_from_html and not phantom_in_html and len(csv_titles) == len(html_titles):
        print(f"  ✓  All {len(csv_titles)} item(s) accounted for — CSV and HTML are in agreement.")
    else:
        if missing_from_html:
            print()
            print(f"  ✗  {len(missing_from_html)} CSV item(s) NOT FOUND in HTML output:")
            for key in sorted(missing_from_html):
                print(f"       – \"{csv_norm[key]}\"")
            print("     → Possible cause: compile error, section mismatch, or title was altered.")
            print("       Review the compile log above for any [WARN] messages on these items.")

        if phantom_in_html:
            print()
            print(f"  ⚠  {len(phantom_in_html)} HTML item(s) have NO matching CSV source row:")
            for key in sorted(phantom_in_html):
                print(f"       – \"{html_norm[key]}\"")
            print("     → Possible cause: leftover output from a previous build, or title")
            print("       was significantly altered by the compiler (check html.escape output).")

        if not missing_from_html and not phantom_in_html and len(csv_titles) != len(html_titles):
            print()
            print(f"  ℹ  Title text matches but counts differ ({len(csv_titles)} CSV vs {len(html_titles)} HTML).")
            print("     → Possible cause: duplicate title in CSV or duplicate render in HTML.")

    print(f"  {DIVIDER}")
    print()


# ---------------------------------------------------------------------------
# HTML diff against previous run snapshot  [ENABLE_HTML_DIFF]
#
# This is an optional convenience feature. Set ENABLE_HTML_DIFF = True at
# the top of this file to activate it.
#
# To remove this feature entirely:
#   1. Delete ENABLE_HTML_DIFF at the top of the file
#   2. Delete this entire block (from the line below to the matching end marker)
#   3. Remove the call to print_html_diff() in run_pipeline_with_retry()
#
# <!-- DIFF_VALIDATION_ENABLED -->
# ---------------------------------------------------------------------------

def _extract_html_structure(html_text: str) -> dict:
    item_anchors  = re.findall(r'id="(item-[^"]+)"', html_text)
    section_names = re.findall(r'class="section-label[^"]*"[^>]*>\s*([^<]+?)\s*<', html_text)
    titles        = re.findall(r'class="section-title[^"]*"[^>]*>\s*([^<]+?)\s*<', html_text)
    return {
        "item_count":    len(item_anchors),
        "section_names": [s.strip() for s in section_names],
        "titles":        [t.strip() for t in titles],
    }


def print_html_diff(pipeline: str) -> None:
    """
    Compare newly compiled HTML structure against the previous run snapshot
    (stored as <output>.prev.html).  Prints additions/removals by section
    and title.  Saves a new snapshot after each run.

    This is a convenience feature, not a build gate.
    Disable by setting ENABLE_HTML_DIFF = False.
    """
    if not ENABLE_HTML_DIFF:
        return

    new_html_path = OUTPUT_FILES[pipeline]
    prev_path     = new_html_path.with_suffix(".prev.html")

    if not new_html_path.exists():
        return

    new_text   = new_html_path.read_text(encoding="utf-8", errors="replace")
    new_struct = _extract_html_structure(new_text)

    print()
    print(f"  {DIVIDER}")
    print(f"  HTML DIFF vs. PREVIOUS RUN  ({pipeline.upper()})")
    print(f"  {DIVIDER}")

    if prev_path.exists():
        prev_text   = prev_path.read_text(encoding="utf-8", errors="replace")
        prev_struct = _extract_html_structure(prev_text)

        delta       = new_struct["item_count"] - prev_struct["item_count"]
        added_sec   = [s for s in new_struct["section_names"] if s not in prev_struct["section_names"]]
        removed_sec = [s for s in prev_struct["section_names"] if s not in new_struct["section_names"]]
        added_t     = [t for t in new_struct["titles"] if t not in prev_struct["titles"]]
        removed_t   = [t for t in prev_struct["titles"] if t not in new_struct["titles"]]

        if delta == 0 and not added_sec and not removed_sec and not added_t and not removed_t:
            print("  No structural changes vs. previous run.")
        else:
            if delta != 0:
                sign = "+" if delta > 0 else ""
                print(f"  Item count  : {sign}{delta}  ({prev_struct['item_count']} → {new_struct['item_count']})")
            for s in added_sec:
                print(f"  + Section   : {s}")
            for s in removed_sec:
                print(f"  - Section   : {s}")
            for t in added_t:
                print(f"  + Title     : {t}")
            for t in removed_t:
                print(f"  - Title     : {t}")
    else:
        print("  (No previous snapshot — this is the first run for comparison.)")
        print(f"  Items in output : {new_struct['item_count']}")
        for s in new_struct["section_names"]:
            print(f"    Section : {s}")

    print(f"  {DIVIDER}")
    print()

    try:
        prev_path.write_text(new_text, encoding="utf-8")
    except Exception:
        pass  # Non-fatal

# <!-- /DIFF_VALIDATION_ENABLED -->


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def run_stage(
    stage: dict,
    issue_date: str,
    logger: logging.Logger,
    callout: str | None = None,
    bottom_callout: str | None = None,
) -> tuple[int, str, str]:
    script = stage["script"]

    if not script.exists():
        msg = f"ERROR: Script not found: {script}"
        logger.error(msg)
        return 1, "", msg

    cmd = [sys.executable, str(script), "--issue-date", issue_date]

    if stage.get("pass_callout"):
        if callout is not None:
            cmd += ["--callout", callout]
        if bottom_callout is not None:
            cmd += ["--bottom-callout", bottom_callout]

    logger.debug(f"  CMD: {' '.join(str(c) for c in cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJ_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        msg = f"ERROR: Failed to launch {script.name}: {e}"
        logger.error(msg)
        return 1, "", msg

    return result.returncode, result.stdout or "", result.stderr or ""


# ---------------------------------------------------------------------------
# VS Code launcher
# ---------------------------------------------------------------------------

def open_in_vscode(pipelines: list[str], no_open: bool, logger: logging.Logger) -> None:
    """
    Open the entire ChucksList_Builder folder in VS Code, then open each
    final HTML output so the operator can review before uploading to Zoho.
    """
    if no_open:
        return
    try:
        subprocess.Popen(f'code "{PROJ_DIR}"', shell=True)
        logger.info(f"  Opened VS Code workspace: {PROJ_DIR.name}")
        for p in pipelines:
            html_file = OUTPUT_FILES[p]
            if html_file.exists():
                subprocess.Popen(f'code "{html_file}"', shell=True)
                logger.info(f"  Opened in VS Code: {html_file.name}")
    except Exception as e:
        logger.debug(f"  VS Code open skipped: {e}")


# ---------------------------------------------------------------------------
# Interactive retry loop
# ---------------------------------------------------------------------------

def run_pipeline_with_retry(
    pipeline: str,
    issue_date: str,
    logger: logging.Logger,
    callout: str | None,
    bottom_callout: str | None,
) -> bool:
    """
    Run one full pipeline (preprocess → compile) with interactive retry.

    On stage failure:
      1. Print the formatted error panel
      2. Prompt: [y] fix + re-run  [n] skip pipeline  [q] quit builder
      3. On [y]: re-run from the failed stage index

    Returns True if all stages passed, False if operator skipped or quit.
    """
    stages      = PIPELINE_STAGES[pipeline]
    stage_index = 0

    while stage_index < len(stages):
        stage = stages[stage_index]
        is_compile = stage.get("pass_callout", False)

        print()
        logger.info(f"  ▶  {stage['name']}")
        print(f"  {DIVIDER}")

        rc, stdout, stderr = run_stage(
            stage, issue_date, logger,
            callout=callout,
            bottom_callout=bottom_callout,
        )

        # Echo clean pass output
        for line in (stdout + "\n" + stderr).splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            lvl = _classify_line(stripped)
            if lvl == "OK":
                print(f"  ✓  {stripped}")
            elif lvl == "AUTO-FIX":
                print(f"  ✔  {stripped}")

        if rc != 0:
            print_error_panel(stage["name"], rc, stdout, stderr)

            while True:
                answer = _prompt(
                    f"  Have you fixed the issue(s) above?\n"
                    f"  [y] Re-run this stage   [n] Skip pipeline   [q] Quit\n"
                    f"  > ",
                    {"y", "n", "q"},
                )
                if answer == "q":
                    print("\n  Builder quit by operator.\n")
                    return False
                if answer == "n":
                    print(f"\n  Skipping remainder of {pipeline.upper()} pipeline.\n")
                    return False
                if answer == "y":
                    print(f"\n  Re-running: {stage['name']}\n")
                    break
            # retry same stage_index
            continue

        # Stage passed
        if is_compile:
            # Real data validation: CSV rows vs HTML rendered items
            validate_csv_vs_html(pipeline)

            # Optional HTML diff vs previous snapshot  <!-- DIFF_VALIDATION_ENABLED -->
            print_html_diff(pipeline)               # <!-- DIFF_VALIDATION_ENABLED -->

        stage_index += 1

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chuck's List publishing pipeline builder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  py Chucks_List_Builder.py --issue-date 2026-05-31\n"
            "  py Chucks_List_Builder.py --issue-date 2026-05-31 --issue-type bulletin\n"
            "  py Chucks_List_Builder.py --issue-date 2026-05-31 --callout \"Special note here\"\n"
            "  py Chucks_List_Builder.py --issue-date 2026-05-31 --log-to-file\n"
        ),
    )
    parser.add_argument("--issue-date", required=True, metavar="YYYY-MM-DD",
                        help="Publication date for this issue")
    parser.add_argument("--issue-type", choices=["bulletin", "events", "both"],
                        default="both", help="Which pipeline(s) to run (default: both)")
    parser.add_argument("--callout", default=None, metavar="TEXT",
                        help="Top callout text — skips the callout wizard")
    parser.add_argument("--bottom-callout", default=None, metavar="TEXT",
                        help="Bottom callout text (only honored when --callout is also provided)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--log-to-file", action="store_true",
                        help="Write build log to logs/build_YYYY-MM-DD_HHMMSS.log")
    parser.add_argument("--no-open-vscode", action="store_true",
                        help="Do not open VS Code after build")
    args = parser.parse_args()

    validate_issue_date(args.issue_date)

    logger = setup_logging(args.log_to_file, args.issue_date)
    if not args.debug:
        logger.setLevel(logging.INFO)

    print()
    print(THICK_DIVIDER)
    print(f"  Chuck's List Builder  ·  Issue: {args.issue_date}")
    print(f"  Pipeline: {args.issue_type}  ·  Root: {PROJ_DIR.name}")
    print(THICK_DIVIDER)

    pipelines: list[str] = []
    if args.issue_type in ("bulletin", "both"):
        pipelines.append("bulletin")
    if args.issue_type in ("events", "both"):
        pipelines.append("events")

    # Enforce design rule: bottom-only change is not allowed
    if args.bottom_callout is not None and args.callout is None:
        print()
        print("  ⚠  NOTE: --bottom-callout was passed without --callout.")
        print("     Design rule: the bottom callout can only be changed when a")
        print("     top callout is also being set. --bottom-callout is ignored.")
        print()
        args.bottom_callout = None

    # Callout wizard (skipped if --callout already on CLI)
    top_callout, bottom_callout = callout_wizard(args.callout, args.bottom_callout)

    # Run pipelines
    failed_pipelines: list[str] = []
    passed_pipelines: list[str] = []

    for pipeline in pipelines:
        print()
        print(THICK_DIVIDER)
        print(f"  {pipeline.upper()} PIPELINE")
        print(THICK_DIVIDER)

        success = run_pipeline_with_retry(
            pipeline, args.issue_date, logger,
            callout=top_callout,
            bottom_callout=bottom_callout,
        )

        if success:
            passed_pipelines.append(pipeline)
        else:
            failed_pipelines.append(pipeline)

    # Build summary
    print()
    print(THICK_DIVIDER)
    print("  BUILD SUMMARY")
    print(THICK_DIVIDER)
    for p in passed_pipelines:
        print(f"  ✓  {p.upper()} — complete")
    for p in failed_pipelines:
        print(f"  ✗  {p.upper()} — did not complete")

    if failed_pipelines:
        print()
        print(f"  {len(failed_pipelines)} pipeline(s) did not complete.")
        print("  Do NOT upload partial output to Zoho.")
        print(THICK_DIVIDER)
        print()
        return 1

    print()
    open_in_vscode(passed_pipelines, args.no_open_vscode, logger)

    print()
    print("  NEXT STEPS")
    print(f"  {DIVIDER}")
    for p in passed_pipelines:
        print(f"  Upload  {OUTPUT_FILES[p].name}  to Zoho Campaigns.")
    print(THICK_DIVIDER)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
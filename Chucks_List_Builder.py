"""
Chucks_List_Builder.py
Role: Single entrypoint for the Chuck's List publishing pipeline.
Canonical command:
    py Chucks_List_Builder.py --issue-date YYYY-MM-DD [--issue-type bulletin|events|both]
                              [--log-to-file] [--no-open-vscode]

Design decisions:
- All paths resolved relative to this file's directory (Path(__file__).resolve().parent).
  This means the command works from any working directory.
- Subprocess stdout/stderr are streamed live AND captured for summary.
- Exit code 0 = all stages passed. Exit code 1 = at least one stage failed.
- Log file written to logs/build_YYYY-MM-DD_HHMMSS.log when --log-to-file is set.
"""

import argparse
import logging
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root — anchored to this file, not to cwd
# ---------------------------------------------------------------------------
PROJ_DIR = Path(__file__).resolve().parent

PIPELINE_STAGES = {
    "bulletin": [
        {
            "name": "Bulletin Preprocess",
            "script": PROJ_DIR / "bulletins" / "preprocess_bulletin_text.py",
        },
        {
            "name": "Bulletin Compile",
            "script": PROJ_DIR / "bulletins" / "compile_bulletin.py",
        },
    ],
    "events": [
        {
            "name": "Events Preprocess",
            "script": PROJ_DIR / "events" / "preprocess_events_text.py",
        },
        {
            "name": "Events Compile",
            "script": PROJ_DIR / "events" / "compile_events.py",
        },
    ],
}

OUTPUT_FILES = {
    "bulletin": PROJ_DIR / "bulletins" / "chucks_bulletin_final_output.html",
    "events":   PROJ_DIR / "events" / "chucks_events_final_output.html",
}


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
    """Fail fast with a helpful message if the date is wrong."""
    try:
        d = date.fromisoformat(issue_date_str)
    except ValueError:
        print(
            f"ERROR: --issue-date '{issue_date_str}' is not a valid date.\n"
            f"  Expected format: YYYY-MM-DD (e.g., 2026-06-07)\n"
            f"  Fix: Check the date and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)
    return d


def run_stage(
    stage: dict,
    issue_date: str,
    logger: logging.Logger,
) -> tuple[int, str, str]:
    """
    Run a single pipeline stage script via subprocess.
    Returns (returncode, stdout_text, stderr_text).
    Streams output live to console AND captures it.
    """
    script: Path = stage["script"]
    name: str    = stage["name"]

    if not script.exists():
        msg = (
            f"ERROR: Script not found: {script}\n"
            f"  Fix: Ensure the file exists at the expected path."
        )
        logger.error(msg)
        return 1, "", msg

    cmd = [sys.executable, str(script), "--issue-date", issue_date]
    logger.info(f"  Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJ_DIR),          # always run from project root
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception as e:
        msg = f"ERROR: Failed to launch {script.name}: {e}"
        logger.error(msg)
        return 1, "", msg

    # Stream captured output to logger
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            logger.info(f"    {line}")
    if result.stderr.strip():
        for line in result.stderr.strip().splitlines():
            # surface warnings as warnings, errors as errors
            if "[WARN]" in line:
                logger.warning(f"    {line}")
            else:
                logger.error(f"    {line}")

    return result.returncode, result.stdout, result.stderr


def open_in_vscode(paths: list[Path], logger: logging.Logger) -> None:
    """Attempt to open output files in VS Code. Non-fatal on failure."""
    try:
        for p in paths:
            if p.exists():
                subprocess.Popen(["code", str(p)], shell=True)
                logger.info(f"  Opened in VS Code: {p.name}")
    except Exception:
        pass  # VS Code open is a convenience, never a build blocker


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chuck's List publishing pipeline builder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          py Chucks_List_Builder.py --issue-date 2026-06-07
          py Chucks_List_Builder.py --issue-date 2026-06-07 --issue-type bulletin
          py Chucks_List_Builder.py --issue-date 2026-06-07 --log-to-file
        """),
    )
    parser.add_argument(
        "--issue-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Publication date for this issue (required)",
    )
    parser.add_argument(
        "--issue-type",
        choices=["bulletin", "events", "both"],
        default="both",
        help="Which pipeline(s) to run (default: both)",
    )
    parser.add_argument(
        "--log-to-file",
        action="store_true",
        help="Write build log to logs/build_YYYY-MM-DD_HHMMSS.log",
    )
    parser.add_argument(
        "--no-open-vscode",
        action="store_true",
        help="Do not open output files in VS Code after build",
    )
    args = parser.parse_args()

    issue_date = validate_issue_date(args.issue_date)
    logger = setup_logging(args.log_to_file, args.issue_date)

    logger.info("=" * 60)
    logger.info(f"Chuck's List Builder — issue date: {args.issue_date}")
    logger.info(f"Pipeline: {args.issue_type}  |  Project root: {PROJ_DIR}")
    logger.info("=" * 60)

    # Determine which pipelines to run
    pipelines = []
    if args.issue_type in ("bulletin", "both"):
        pipelines.append("bulletin")
    if args.issue_type in ("events", "both"):
        pipelines.append("events")

    failed_stages = []
    passed_stages = []

    for pipeline in pipelines:
        logger.info(f"\n── {pipeline.upper()} PIPELINE ──")
        for stage in PIPELINE_STAGES[pipeline]:
            logger.info(f"\n  Stage: {stage['name']}")
            rc, stdout, stderr = run_stage(stage, args.issue_date, logger)
            if rc != 0:
                logger.error(
                    f"  FAILED: {stage['name']} exited with code {rc}.\n"
                    f"  Stopping {pipeline} pipeline. Fix the errors above and re-run."
                )
                failed_stages.append(stage["name"])
                break  # stop this pipeline on first failure
            else:
                passed_stages.append(stage["name"])

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("BUILD SUMMARY")
    logger.info("=" * 60)
    for s in passed_stages:
        logger.info(f"  ✓  {s}")
    for s in failed_stages:
        logger.error(f"  ✗  {s}")

    if not failed_stages:
        logger.info("\nAll stages passed.")
        # Open outputs in VS Code
        if not args.no_open_vscode:
            outputs = [OUTPUT_FILES[p] for p in pipelines if OUTPUT_FILES[p].exists()]
            if outputs:
                open_in_vscode(outputs, logger)
        logger.info("\nNext steps:")
        for p in pipelines:
            out = OUTPUT_FILES[p]
            logger.info(f"  Upload {out.name} to Zoho Campaigns ({p} staging folder).")
        return 0
    else:
        logger.error(
            f"\n{len(failed_stages)} stage(s) failed. "
            f"Review errors above. No partial output should be uploaded to Zoho."
        )
        return 1


if __name__ == "__main__":
    import textwrap
    sys.exit(main())
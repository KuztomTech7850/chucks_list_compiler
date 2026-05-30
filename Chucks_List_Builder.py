import argparse
import logging
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

PROJ_DIR = Path(__file__).resolve().parent

PIPELINE_STAGES = {
    "bulletin": [
        {"name": "Bulletin Preprocess", "script": PROJ_DIR / "bulletins" / "preprocess_bulletin_text.py"},
        {"name": "Bulletin Compile",    "script": PROJ_DIR / "bulletins" / "compile_bulletin.py"},
    ],
    "events": [
        {"name": "Events Preprocess", "script": PROJ_DIR / "events" / "preprocess_events_text.py"},
        {"name": "Events Compile",    "script": PROJ_DIR / "events" / "compile_events.py"},
    ],
}

OUTPUT_FILES = {
    "bulletin": PROJ_DIR / "bulletins" / "chucks_bulletin_final_output.html",
    "events":   PROJ_DIR / "events"    / "chucks_events_final_output.html",
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
    try:
        return date.fromisoformat(issue_date_str)
    except ValueError:
        print(
            f"ERROR: --issue-date '{issue_date_str}' is not a valid date.\n"
            f"  Expected format: YYYY-MM-DD (e.g., 2026-06-07)",
            file=sys.stderr,
        )
        sys.exit(1)


def run_stage(stage: dict, issue_date: str, logger: logging.Logger) -> tuple:
    """
    Run one pipeline stage subprocess.
    Returns (returncode, stdout, stderr).
    errors="replace" prevents Python 3.14 reader thread crash on non-UTF-8
    bytes (0xa0 non-breaking spaces) emitted by compile scripts on Windows.
    stdout/stderr default to "" if None to prevent AttributeError on .strip().
    """
    script = stage["script"]
    name   = stage["name"]

    if not script.exists():
        msg = f"ERROR: Script not found: {script}"
        logger.error(msg)
        return 1, "", msg

    cmd = [sys.executable, str(script), "--issue-date", issue_date]
    logger.info(f"  Running: {' '.join(str(c) for c in cmd)}")

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

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if stdout.strip():
        for line in stdout.strip().splitlines():
            logger.info(f"    {line}")
    if stderr.strip():
        for line in stderr.strip().splitlines():
            if "[WARN]" in line:
                logger.warning(f"    {line}")
            else:
                logger.error(f"    {line}")

    return result.returncode, stdout, stderr


def open_in_vscode(paths: list, logger: logging.Logger) -> None:
    """Non-fatal convenience open. shell=True needed on Windows for 'code' alias."""
    try:
        for p in paths:
            if p.exists():
                subprocess.Popen(f'code "{p}"', shell=True)
                logger.info(f"  Opened in VS Code: {p.name}")
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chuck's List publishing pipeline builder.",
        epilog=(
            "Examples:\n"
            "  py Chucks_List_Builder.py --issue-date 2026-06-07\n"
            "  py Chucks_List_Builder.py --issue-date 2026-06-07 --issue-type bulletin\n"
            "  py Chucks_List_Builder.py --issue-date 2026-06-07 --log-to-file\n"
        ),
    )
    parser.add_argument("--issue-date", required=True, metavar="YYYY-MM-DD",
                        help="Publication date for this issue")
    parser.add_argument("--issue-type", choices=["bulletin", "events", "both"],
                        default="both", help="Which pipeline(s) to run (default: both)")
    parser.add_argument("--log-to-file", action="store_true",
                        help="Write build log to logs/build_YYYY-MM-DD_HHMMSS.log")
    parser.add_argument("--no-open-vscode", action="store_true",
                        help="Do not open output files in VS Code after build")
    args = parser.parse_args()

    validate_issue_date(args.issue_date)
    logger = setup_logging(args.log_to_file, args.issue_date)

    logger.info("=" * 60)
    logger.info(f"Chuck's List Builder -- issue date: {args.issue_date}")
    logger.info(f"Pipeline: {args.issue_type}  |  Project root: {PROJ_DIR}")
    logger.info("=" * 60)

    pipelines = []
    if args.issue_type in ("bulletin", "both"):
        pipelines.append("bulletin")
    if args.issue_type in ("events", "both"):
        pipelines.append("events")

    failed_stages = []
    passed_stages = []

    for pipeline in pipelines:
        logger.info(f"\n-- {pipeline.upper()} PIPELINE --")
        for stage in PIPELINE_STAGES[pipeline]:
            logger.info(f"\n  Stage: {stage['name']}")
            rc, stdout, stderr = run_stage(stage, args.issue_date, logger)
            if rc != 0:
                logger.error(
                    f"  FAILED: {stage['name']} exited with code {rc}.\n"
                    f"  Stopping {pipeline} pipeline. Fix errors above and re-run."
                )
                failed_stages.append(stage["name"])
                break
            else:
                passed_stages.append(stage["name"])

    logger.info("\n" + "=" * 60)
    logger.info("BUILD SUMMARY")
    logger.info("=" * 60)
    for s in passed_stages:
        logger.info(f"  [OK]   {s}")
    for s in failed_stages:
        logger.error(f"  [FAIL] {s}")

    if not failed_stages:
        logger.info("\nAll stages passed.")
        if not args.no_open_vscode:
            outputs = [OUTPUT_FILES[p] for p in pipelines if OUTPUT_FILES[p].exists()]
            open_in_vscode(outputs, logger)
        logger.info("\nNext steps:")
        for p in pipelines:
            logger.info(f"  Upload {OUTPUT_FILES[p].name} to Zoho Campaigns.")
        return 0
    else:
        logger.error(
            f"\n{len(failed_stages)} stage(s) failed. "
            f"Do not upload partial output to Zoho."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
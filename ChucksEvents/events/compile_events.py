"""
events/compile_events.py
Role: Compile events_data.csv -> chucks_events_final_output.html
Pipeline stage: COMPILE (runs after preprocess_events_text.py)
Called by: Chucks_List_Builder.py via subprocess

Engineer notes:
- This compiler assumes preprocess_events_text.py has already normalized and
  validated the data.
- Compile is responsible for organizing and rendering the massaged event rows
  into the approved EVENTS email template (same family as the Bulletin template).
- Image file existence is NOT validated here by design for the current local
  workflow. The HTML is often relocated after compile, and the CSV Image value
  is treated as trusted. If/when this pipeline is migrated to a server, restore
  strict image/path validation there.
- Markdown links [Label](https://example.com) are supported and preferred.
- Bare URLs/emails are linkified only after escaping.

IMAGE HANDLING CONTRACT
  The HTML output file is bundled with an Images/ subfolder at the same level
  (e.g. ChucksEvents/Issue.html + ChucksEvents/Images/photo.jpg).
  All image src/href values are emitted as:

      Images/filename.ext

  using forward slashes (never Windows backslashes), and the filename is
  preserved exactly as entered — no normalization of spaces-to-underscores
  or case changes. The file extension is passed through as-is.

  Multi-image pipe syntax: "Images/a.jpg|Images/b.png" is split on | and
  each entry rendered as its own <img>/<a> block. Max 3 images per entry;
  a 4th triggers [WARN] and is dropped. A missing Images/ prefix triggers
  [WARN] and is auto-prepended so src paths are consistent.

CHANGELOG
  2026-05-31  Bug 2 fix: compile side was not affected by QUOTE_ALL fix, but
              MARKDOWN_LINK_RE and escape-then-linkify pipeline confirmed.
  2026-06-01  P1-B / Bug 5: add to_web_path() helper — all asset src= and href=
              values normalized via Path.as_posix() + urllib.parse.quote; no
              Windows backslash paths emitted into HTML.
              Bug 6: build_image_html() now splits Image field on '|' and
              renders one <img>/<a> pair per filename. MAX_INLINE_IMAGES = 3
              enforced with [WARN]. Both src and href for the same image use
              the identical normalized path.
              Image filename preservation: filenames are passed through as-is;
              no character substitution (spaces stay spaces, case preserved,
              extension preserved). Only the path separator is normalized.
              Auto-prepend Images/ prefix if caller omitted it.
              read_rows() now returns None on hard CSV error (vs [] which was
              indistinguishable from "valid but empty").
              Top callout block is suppressed entirely when --callout is not
              passed, matching compile_bulletin.py behavior.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from pathlib import Path
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR  = Path(__file__).resolve().parent
PROJ_DIR    = SCRIPT_DIR.parent
INPUT_CSV   = SCRIPT_DIR / "events_data.csv"
OUTPUT_DIR  = PROJ_DIR
OUTPUT_HTML = SCRIPT_DIR / "chucks_events_final_output.html"

MAX_INLINE_IMAGES = 3

# ---------------------------------------------------------------------------
# Section structure
# ---------------------------------------------------------------------------

SECTION_ORDER = [
    "Single Events",
    "Hosts with Multiple Events",
    "Recurring Events",
]

SECTION_ALIASES = {
    "Single":                    "Single Events",
    "Single Events":             "Single Events",
    "Multiple":                  "Hosts with Multiple Events",
    "Multiple Events":           "Hosts with Multiple Events",
    "Hosts with Multiple Events":"Hosts with Multiple Events",
    "Recurring":                 "Recurring Events",
    "Recurring Events":          "Recurring Events",
}

SECTION_ID_MAP = {
    "Single Events":              "section-single-events",
    "Hosts with Multiple Events": "section-hosts-with-multiple-events",
    "Recurring Events":           "section-recurring-events",
}

# ---------------------------------------------------------------------------
# Callout defaults
# ---------------------------------------------------------------------------

# Top callout: render only if the operator passes --callout.
# If omitted, the block is suppressed entirely.
DEFAULT_TOP_CALLOUT = ""

# Bottom callout: always rendered. Override with --bottom-callout if needed.
DEFAULT_BOTTOM_CALLOUT = (
    "Be cautious of offers that ask for advance payment or personal information. "
    "Chuck's List is community-run; use your judgment, meet in public spaces when "
    "possible, and check references when needed."
)

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

TRAILING_PUNCTUATION = ".,;:!?)}]"

MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]\n]{1,300})\]\((https?://[^\s)]+|mailto:[^\s)]+)\)",
    re.IGNORECASE,
)
BULLET_LINE_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
SUBHEAD_RE     = re.compile(r"^\s*##\s*(.+?)\s*$")

# ---------------------------------------------------------------------------
# Frozen CSS template (Mesa Verde / Montezuma palette — do not alter)
# ---------------------------------------------------------------------------

EMAIL_CSS = """
    /* ---------- Base reset ---------- */
    body, table, td, p, a {
      margin: 0;
      padding: 0;
      -webkit-text-size-adjust: 100% !important;
      -ms-text-size-adjust: 100% !important;
      text-size-adjust: 100% !important;
    }

    table {
      border-collapse: collapse;
      border-spacing: 0;
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
    }

    img {
      border: 0;
      outline: none;
      text-decoration: none;
      display: block;
      max-width: 100%;
      height: auto;
      -ms-interpolation-mode: bicubic;
    }

    body {
      width: 100% !important;
      min-width: 100%;
      background-color: #f5efe4;
      color: #221d17;
      font-family: Arial, Helvetica, sans-serif;
    }

    a {
      color: #b66324;
      text-decoration: underline;
    }

    .wrapper {
      width: 100%;
      background-color: #f5efe4;
    }

    .container {
      width: 100%;
      max-width: 720px;
      background-color: #fdf9f3;
      border: 1px solid #d9cfc0;
    }

    .preheader {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
      line-height: 22px;
      color: #665b50;
    }

    .hidden-preheader {
      display: none !important;
      visibility: hidden;
      opacity: 0;
      color: transparent;
      height: 0;
      width: 0;
      overflow: hidden;
      mso-hide: all;
      font-size: 1px;
      line-height: 1px;
      max-height: 0;
      max-width: 0;
    }

    .header-band,
    .footer-band {
      background-color: #2b3d2e;
    }

    .header-band {
      border-bottom: 4px solid #b66324;
    }

    .footer-band {
      border-top: 3px solid #c1732a;
    }

    .eyebrow {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 12px;
      line-height: 18px;
      text-transform: uppercase;
      letter-spacing: 1.4px;
      font-weight: bold;
      color: #b8c3ab;
    }

    .headline {
      font-family: Georgia, "Times New Roman", Times, serif;
      font-size: 28px;
      line-height: 36px;
      font-weight: bold;
      color: #f5efe4;
    }

    .header-body-copy {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 18px;
      line-height: 28px;
      color: #d7cec0;
    }

    .section-label {
      background-color: #3d6b72;
      border-top: 1px solid #2e5259;
      border-bottom: 1px solid #2e5259;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 13px;
      line-height: 18px;
      text-transform: uppercase;
      letter-spacing: 1.3px;
      font-weight: bold;
      color: #e8f3f4;
    }

    .row-white {
      background-color: #fdf9f3;
    }

    .row-alt {
      background-color: #f7f2e8;
    }

    .section-title {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 22px;
      line-height: 30px;
      font-weight: bold;
      color: #1a1612;
    }

    .date-line {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 18px;
      line-height: 28px;
      font-weight: bold;
      color: #b66324;
    }

    .body-copy,
    .body-copy p,
    .body-copy li {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 20px;
      line-height: 30px;
      color: #221d17;
    }

    .small-label {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 13px;
      line-height: 20px;
      font-weight: bold;
      color: #54623f;
      text-transform: uppercase;
      letter-spacing: 0.6px;
    }

    .meta-line {
      padding-top: 10px;
      font-size: 20px;
      line-height: 30px;
      color: #221d17;
      font-family: Arial, Helvetica, sans-serif;
    }

    .callout {
      background-color: #eef2e8;
      border-left: 4px solid #6b7c52;
      border-top: 1px solid #c8d4b8;
      border-right: 1px solid #c8d4b8;
      border-bottom: 1px solid #c8d4b8;
      padding: 16px;
    }

    .footer-copy {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 13px;
      line-height: 21px;
      color: #b8c3ab;
    }

    .footer-copy a {
      color: #e19a60;
    }

    .divider {
      border-top: 1px solid #d9cfc0;
      font-size: 0;
      line-height: 0;
    }

    .entry-subhead {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 18px;
      line-height: 28px;
      font-weight: bold;
      color: #54623f;
      margin: 14px 0 4px 0;
    }

    .body-copy ul {
      margin: 10px 0 10px 24px;
      padding: 0;
    }

    .body-copy li {
      margin: 0 0 6px 0;
    }

    @media (prefers-color-scheme: dark) {
      body, .wrapper {
        background-color: #141413 !important;
      }

      .container {
        background-color: #1e221b !important;
        border-color: #2f322b !important;
      }

      .preheader {
        color: #95897c !important;
      }

      .header-band,
      .footer-band {
        background-color: #1a241b !important;
      }

      .headline {
        color: #f3eadb !important;
      }

      .header-body-copy {
        color: #b7ad9f !important;
      }

      .section-label {
        background-color: #244145 !important;
        border-color: #192d30 !important;
        color: #d6edf0 !important;
      }

      .row-white {
        background-color: #232924 !important;
      }

      .row-alt {
        background-color: #1e221c !important;
      }

      .section-title {
        color: #eedfc8 !important;
      }

      .date-line {
        color: #e19a60 !important;
      }

      .body-copy,
      .body-copy p,
      .body-copy li,
      .meta-line {
        color: #d3c7b8 !important;
      }

      .small-label {
        color: #9bb27c !important;
      }

      .callout {
        background-color: #1a241b !important;
        border-left-color: #6b7c52 !important;
        border-top-color: #31422f !important;
        border-right-color: #31422f !important;
        border-bottom-color: #31422f !important;
      }

      .divider {
        border-top-color: #384038 !important;
      }

      a {
        color: #e19a60 !important;
      }
    }

    @media only screen and (max-width: 620px) {
      .container {
        width: 100% !important;
      }

      .mobile-pad {
        padding-left: 16px !important;
        padding-right: 16px !important;
      }

      .headline {
        font-size: 24px !important;
        line-height: 32px !important;
      }

      .section-title {
        font-size: 20px !important;
        line-height: 28px !important;
      }

      .header-body-copy {
        font-size: 17px !important;
        line-height: 27px !important;
      }

      .body-copy,
      .body-copy p,
      .body-copy li,
      .meta-line,
      .date-line {
        font-size: 19px !important;
        line-height: 29px !important;
      }
    }
"""

# ---------------------------------------------------------------------------
# Asset path helper (Bug 5 fix)
# ---------------------------------------------------------------------------

def to_web_path(path: str) -> str:
    """
    Normalize a filesystem path or relative filename to a forward-slash URL
    path safe for use in HTML src= and href= attributes.

    - Path.as_posix() converts Windows backslashes to forward slashes.
    - urllib.parse.quote percent-encodes characters that are not safe in a
      URL path component. The safe= set preserves characters that are legal
      and meaningful in a relative web path, including spaces encoded
      properly — but note: spaces in filenames will become %20, which is
      correct for a URL path and will resolve correctly when the HTML and
      Images/ folder are co-located (e.g. in a ZIP bundle).

    IMPORTANT: This function does NOT change the filename itself — it only
    normalizes the path separator and percent-encodes URL-unsafe characters.
    The stem and extension are preserved exactly as entered in the CSV.
    """
    return quote(Path(path).as_posix(), safe="/:._-~")


def ensure_images_prefix(raw_entry: str) -> tuple[str, bool]:
    """
    Ensure the image path starts with 'Images/' (case-sensitive, matching the
    canonical Images/ subfolder that is bundled alongside the output HTML).

    If the path already has a scheme (http/https) it is returned as-is.
    If the path does not start with 'Images/' it is prepended and a warning
    flag is returned so the caller can emit [WARN].

    The filename itself (stem + extension) is NEVER altered.
    """
    stripped = raw_entry.strip()

    if stripped.lower().startswith(("http://", "https://")):
        return stripped, False

    # Normalize any leading path separators without touching the filename
    posix = Path(stripped).as_posix()

    # Already has an Images/ prefix (case-sensitive to match actual folder)
    if posix.startswith("Images/"):
        return stripped, False

    # Strip any other leading directory components the operator may have
    # accidentally included, then re-prefix with Images/
    filename_only = Path(posix).name
    return f"Images/{filename_only}", True


# ---------------------------------------------------------------------------
# Anchor, link, and text helpers
# ---------------------------------------------------------------------------

def make_anchor(title: str, seen: dict[str, int]) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    slug = slug[:60] or "item"
    slug = f"item-{slug}"
    count = seen.get(slug, 0) + 1
    seen[slug] = count
    return slug if count == 1 else f"{slug}-{count}"


def split_trailing_punctuation(token: str) -> tuple[str, str]:
    clean = token.rstrip(TRAILING_PUNCTUATION)
    trailing = token[len(clean):]
    return clean, trailing


def protect_markdown_links(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    counter = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        label = html.escape(match.group(1).strip())
        href  = html.escape(match.group(2).strip(), quote=True)
        token = f"__MDLINK_{counter}__"

        if href.lower().startswith("mailto:"):
            replacements[token] = f'<a href="{href}">{label}</a>'
        else:
            replacements[token] = (
                f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'
            )
        return token

    return MARKDOWN_LINK_RE.sub(repl, text), replacements


def restore_markdown_links(text: str, replacements: dict[str, str]) -> str:
    for token, replacement in replacements.items():
        text = text.replace(token, replacement)
    return text


def linkify_escaped_text(escaped_text: str) -> str:
    token_re = re.compile(
        r"(https?://[^\s<>\"]+|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})"
    )

    parts = token_re.split(escaped_text)
    out: list[str] = []

    for part in parts:
        if not part:
            continue

        clean, trailing = split_trailing_punctuation(part)

        if re.match(r"^https?://", clean, re.IGNORECASE):
            out.append(
                f'<a href="{clean}" target="_blank" rel="noopener noreferrer">{clean}</a>{trailing}'
            )
        elif re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", clean):
            out.append(f'<a href="mailto:{clean}">{clean}</a>{trailing}')
        else:
            out.append(part)

    return "".join(out)


def escape_then_linkify(text: str) -> str:
    protected, replacements = protect_markdown_links(text)
    escaped = html.escape(protected)
    linked  = linkify_escaped_text(escaped)
    return restore_markdown_links(linked, replacements)


# ---------------------------------------------------------------------------
# Body renderer
# ---------------------------------------------------------------------------

def render_body(raw_text: str) -> str:
    if not raw_text or not raw_text.strip():
        return ""

    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = re.split(r"\n{2,}", normalized)
    html_blocks: list[str] = []

    for block in blocks:
        lines = [line.rstrip() for line in block.split("\n")]
        if not any(line.strip() for line in lines):
            continue

        paragraph_lines: list[str] = []
        list_items: list[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph_lines
            if not paragraph_lines:
                return
            joined = "<br>\n".join(escape_then_linkify(line) for line in paragraph_lines)
            html_blocks.append(f'<p style="margin:0 0 14px 0;line-height:1.7;">{joined}</p>')
            paragraph_lines = []

        def flush_list() -> None:
            nonlocal list_items
            if not list_items:
                return
            items = "".join(f'<li style="margin-bottom:6px;">{item}</li>' for item in list_items)
            html_blocks.append(
                f'<ul style="margin:0 0 14px 0;padding-left:22px;">{items}</ul>'
            )
            list_items = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                flush_list()
                continue

            subhead_match = SUBHEAD_RE.match(line)
            bullet_match  = BULLET_LINE_RE.match(line)

            if subhead_match:
                flush_paragraph()
                flush_list()
                html_blocks.append(
                    f'<div class="entry-subhead">'
                    f'{escape_then_linkify(subhead_match.group(1).strip())}'
                    f'</div>'
                )
                continue

            if bullet_match:
                flush_paragraph()
                list_items.append(escape_then_linkify(bullet_match.group(1).strip()))
                continue

            flush_list()
            paragraph_lines.append(line)

        flush_paragraph()
        flush_list()

    return "\n".join(html_blocks)


# ---------------------------------------------------------------------------
# Image renderer (Bug 5 + Bug 6 fix)
# ---------------------------------------------------------------------------

def build_image_html(image_field: str, title: str) -> str:
    """
    Render one <img>/<a> block per pipe-delimited entry in image_field.

    Pipeline:
      1. Split on '|'
      2. Strip whitespace from each entry
      3. Ensure each entry has an 'Images/' prefix (auto-prepend with [WARN]
         if missing, unless it is a full http/https URL)
      4. Normalize path to forward-slash URL syntax via to_web_path()
         — filename stem and extension are preserved exactly as-is
      5. html.escape() the normalized path for safe injection into src= / href=
      6. Both src and href for the same image use the identical normalized path
      7. Truncate at MAX_INLINE_IMAGES with [WARN]

    Why to_web_path() preserves filenames:
      Path("Images/My Photo.JPG").as_posix() == "Images/My Photo.JPG"
      quote("Images/My Photo.JPG", safe="/:._-~") == "Images/My%20Photo.JPG"
    The stem ("My Photo") and extension (".JPG") are untouched; only the
    space is percent-encoded so it is a valid URL path segment.
    """
    if not image_field or not image_field.strip():
        return ""

    # Split and clean raw pipe-delimited entries
    raw_entries = [e.strip() for e in image_field.split("|") if e.strip()]

    if not raw_entries:
        return ""

    # Enforce MAX_INLINE_IMAGES
    if len(raw_entries) > MAX_INLINE_IMAGES:
        print(
            f"  [WARN] Image field has {len(raw_entries)} entries "
            f"(max {MAX_INLINE_IMAGES}). "
            f"Entries beyond position {MAX_INLINE_IMAGES} were dropped. "
            "Fix: use a markdown link in the Body field for the additional image(s).",
            file=sys.stderr,
        )
        raw_entries = raw_entries[:MAX_INLINE_IMAGES]

    alt = html.escape(title, quote=True)
    blocks: list[str] = []

    for raw_entry in raw_entries:
        # Auto-prepend Images/ if the path lacks it and is not a full URL
        normalized_entry, was_fixed = ensure_images_prefix(raw_entry)
        if was_fixed:
            print(
                f"  [WARN] Image path '{raw_entry}' is missing the 'Images/' prefix. "
                f"Auto-corrected to '{normalized_entry}'. "
                "Fix: prefix image filenames with 'Images/' in the CSV.",
                file=sys.stderr,
            )

        # Convert to safe URL path — preserves filename/extension, fixes separators
        web_path = to_web_path(normalized_entry)

        # Escape for safe HTML attribute injection
        # Both src and href use the identical escaped path (Bug 5 contract)
        escaped_path = html.escape(web_path, quote=True)

        blocks.append(
            f"""
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                       style="width:100%; background-color:#efe8dc; border:1px solid #d9cfc0; margin-top:14px;">
                  <tr>
                    <td style="padding:12px;">
                      <a href="{escaped_path}" target="_blank" rel="noopener noreferrer"
                         style="display:block; text-decoration:none;">
                        <img src="{escaped_path}"
                             alt="{alt}"
                             style="display:block; width:100%; max-width:100%; height:auto; border-radius:4px;">
                      </a>
                    </td>
                  </tr>
                </table>""".rstrip()
        )

    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------

def read_rows() -> list[tuple[int, dict[str, str]]] | None:
    """
    Returns:
      list of (row_number, row_dict) tuples — may be empty if CSV is valid but
      has no data rows (all filtered out upstream; not an error here).
      None — hard error (file missing, unreadable, or structurally broken).

    Returning None vs [] lets compile_events() distinguish "hard failure"
    from "legitimately empty after date filter."
    """
    if not INPUT_CSV.exists():
        print(f"ERROR: Input CSV not found: {INPUT_CSV}", file=sys.stderr)
        return None

    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print(
                    "ERROR: events_data.csv appears empty or has no header row.",
                    file=sys.stderr,
                )
                return None

            required_cols = {"Title", "Body", "Starts", "Ends"}
            actual_cols   = set(reader.fieldnames)
            missing       = required_cols - actual_cols
            if missing:
                print(
                    "ERROR: events_data.csv is missing required columns: "
                    f"{', '.join(sorted(missing))}\n"
                    f"  Found columns: {', '.join(sorted(actual_cols))}\n"
                    "  Fix: Re-export from Chucks-list-MASTER.ods and re-run preprocess.",
                    file=sys.stderr,
                )
                return None

            return [(i, row) for i, row in enumerate(reader, start=2)]

    except UnicodeDecodeError:
        print(
            "ERROR: events_data.csv is not valid UTF-8. "
            "Re-run preprocess with UTF-8 output.",
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        print(f"ERROR reading {INPUT_CSV}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Section grouper
# ---------------------------------------------------------------------------

def group_rows(
    rows: list[tuple[int, dict[str, str]]]
) -> list[tuple[str, list[tuple[int, dict[str, str]]]]]:
    grouped: dict[str, list[tuple[int, dict[str, str]]]] = {
        name: [] for name in SECTION_ORDER
    }

    for row_num, row in rows:
        raw_section = (row.get("Section") or "").strip()
        section     = SECTION_ALIASES.get(raw_section, raw_section)
        title       = (row.get("Title") or "").strip()

        if not title:
            print(
                f"  [WARN] Row {row_num}: field 'Title' is empty. "
                "Fix: enter a title. Item skipped.",
                file=sys.stderr,
            )
            continue

        if not section:
            section = "Single Events"

        if section not in SECTION_ORDER:
            print(
                f"  [WARN] Row {row_num}: field 'Section' has value '{raw_section}' "
                f"for item '{title}'. "
                f"Fix: use one of: {', '.join(SECTION_ORDER)}. Item skipped.",
                file=sys.stderr,
            )
            continue

        grouped[section].append((row_num, row))

    return [
        (section, grouped[section])
        for section in SECTION_ORDER
        if grouped[section]
    ]


# ---------------------------------------------------------------------------
# TOC renderer
# ---------------------------------------------------------------------------

def build_toc_html(
    grouped_sections: list[tuple[str, list[tuple[int, dict[str, str]]]]],
    item_anchor_map: dict[tuple[str, int], str],
) -> str:
    lines: list[str] = []

    for section_name, items in grouped_sections:
        section_id = SECTION_ID_MAP[section_name]
        lines.append(
            f'<li style="list-style:none; margin-top:10px;">'
            f'<strong><a href="#{section_id}">{html.escape(section_name)}</a></strong>'
            f'</li>'
        )
        for row_num, row in items:
            title  = (row.get("Title") or "").strip()
            anchor = item_anchor_map[(section_name, row_num)]
            lines.append(
                f'<li><a href="#{anchor}">{html.escape(title)}</a></li>'
            )

    return (
        '<div class="body-copy" style="font-size:18px; line-height:26px;">'
        '<strong>In this Events edition</strong>'
        '</div>'
        '<div class="body-copy" style="padding-top:8px; font-size:18px; line-height:26px;">'
        f'<ul style="margin:8px 0 0 20px; padding:0;">{"".join(lines)}</ul>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Full HTML assembly
# ---------------------------------------------------------------------------

def build_full_html(
    issue_date: str,
    toc_html: str,
    section_blocks: list[str],
    top_callout: str,
    bottom_callout: str,
) -> str:
    body_sections = "\n".join(section_blocks)

    # Top callout is suppressed entirely when the operator did not pass --callout
    top_callout_block = ""
    if top_callout and top_callout.strip():
        top_callout_block = f"""
            <tr>
              <td class="row-white mobile-pad" style="padding:18px 28px;">
                <div class="callout body-copy">
                  {escape_then_linkify(top_callout)}
                </div>
              </td>
            </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="format-detection" content="telephone=no,address=no,email=no,date=no,url=no">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>Chuck's List Events &mdash; {html.escape(issue_date)}</title>
  <style type="text/css">
{EMAIL_CSS}
  </style>
</head>

<body style="margin:0; padding:0; background-color:#f5efe4;">
  <div class="hidden-preheader">
    Community Events for our local area, in and around Montezuma County.
  </div>

  <center class="wrapper" style="width:100%; background-color:#f5efe4;">

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; background-color:#f5efe4;">
      <tr>
        <td align="center" style="padding:18px 12px 8px 12px;">
          <table role="presentation" class="container" width="720" cellpadding="0" cellspacing="0" border="0" style="width:100%; max-width:720px; background-color:#fdf9f3; border:1px solid #d9cfc0;">
            <tr>
              <td class="preheader mobile-pad" align="center" style="padding:14px 20px;">
                Can't read this email easily?
                <a href="$[LI:VIEWINBROWSER]$" target="_blank" rel="noopener noreferrer" style="color:#b66324; text-decoration:underline;">View this email in a browser</a>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; background-color:#f5efe4;">
      <tr>
        <td align="center" style="padding:0 12px 18px 12px;">
          <table role="presentation" class="container" width="720" cellpadding="0" cellspacing="0" border="0">

            <tr>
              <td class="header-band mobile-pad" style="padding:28px 28px 26px 28px;">
                <div class="eyebrow">
                  Chuck's List &mdash; Events
                </div>

                <div class="headline" style="padding-top:8px;">
                  Upcoming local community events
                </div>

                <div class="header-body-copy" style="padding-top:12px;">
                  Upcoming local events in and around Montezuma County for neighbors, families, and visitors. Libraries, museums, parks, nonprofits, schools, and other local hosts are invited to submit events for free inclusion in this digest.
                </div>

                <div class="header-body-copy" style="padding-top:10px; font-size:15px; line-height:22px;">
                  Send your post to <a href="mailto:ChucksList@McAfeeFarm.biz" style="color:#e19a60; text-decoration:underline;">ChucksList@McAfeeFarm.biz</a> or reply to this email.
                </div>

                <div class="header-body-copy" style="padding-top:10px; font-size:15px; line-height:22px;">
                  Issue date: {html.escape(issue_date)}
                </div>
              </td>
            </tr>

            <tr>
              <td class="row-white mobile-pad" style="padding:18px 28px 8px 28px;">
                {toc_html}
              </td>
            </tr>

            {top_callout_block}

            {body_sections}

            <tr>
              <td class="row-white mobile-pad" style="padding:22px 28px;">
                <div class="callout body-copy">
                  {escape_then_linkify(bottom_callout)}
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 0 0 0; background-color:#f5efe4;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; background-color:#2b3d2e; border-top:3px solid #c1732a;" class="footer-band">
                  <tr>
                    <td class="mobile-pad footer-copy" align="center" style="padding:20px 24px 6px 24px;">
                      This email was sent by
                      <a href="mailto:ChucksList@McAfeeFarm.biz" style="color:#e89050; text-decoration:underline;">ChucksList@McAfeeFarm.biz</a>
                      to
                      <a href="mailto:$[UD:CONTACT_EMAIL]$" style="color:#e89050; text-decoration:underline;">$[UD:CONTACT_EMAIL]$</a>
                    </td>
                  </tr>
                  <tr>
                    <td class="mobile-pad footer-copy" align="center" style="padding:6px 24px;">
                      Not interested?
                      <a href="$[LI:UNSUBSCRIBE]$" target="_blank" rel="noopener noreferrer" style="color:#e89050; text-decoration:underline;">Unsubscribe</a>
                    </td>
                  </tr>
                  <tr>
                    <td class="mobile-pad footer-copy" align="center" style="padding:6px 24px;">
                      Feedback or corrections:
                      <a href="mailto:THill@techspecific.com" style="color:#e89050; text-decoration:underline;">THill@techspecific.com</a>
                      &nbsp;&middot;&nbsp;
                      <a href="mailto:Chuck@mcafeefarm.biz" style="color:#e89050; text-decoration:underline;">Chuck@mcafeefarm.biz</a>
                    </td>
                  </tr>
                  <tr>
                    <td class="mobile-pad footer-copy" align="center" style="padding:6px 24px 24px 24px;">
                      Chuck's List powered by
                      <a href="https://www.techspecific.com" target="_blank" rel="noopener noreferrer" style="color:#e89050; text-decoration:underline;">TechSpecific&trade;</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </center>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Compile entrypoint
# ---------------------------------------------------------------------------

def compile_events(
    issue_date: str,
    callout: str | None = None,
    bottom_callout: str | None = None,
) -> int:
    rows = read_rows()

    # Hard CSV error — None means the file is missing or structurally broken
    if rows is None:
        return 1

    # Valid but empty — not an error; nothing to publish this cycle
    if not rows:
        print(
            f"  [WARN] events_data.csv has no data rows for issue date {issue_date}. "
            "The output will be an empty events email.",
            file=sys.stderr,
        )

    def sort_key(item: tuple[int, dict[str, str]]) -> tuple[str, str]:
        _, row = item
        return (
            (row.get("Starts") or "9999-99-99"),
            (row.get("Title") or "").strip().lower(),
        )

    rows.sort(key=sort_key)
    grouped_sections = group_rows(rows)

    seen_anchors:    dict[str, int]             = {}
    item_anchor_map: dict[tuple[str, int], str] = {}

    for section_name, items in grouped_sections:
        for row_num, row in items:
            title = (row.get("Title") or "").strip()
            item_anchor_map[(section_name, row_num)] = make_anchor(title, seen_anchors)

    toc_html = build_toc_html(grouped_sections, item_anchor_map)

    section_blocks: list[str] = []
    alternating_index = 0

        for section_name, items in grouped_sections:
        section_blocks.append(
            f"""
            <tr id="{SECTION_ANCHORS[section_name]}">
              <td class="section-label mobile-pad" style="padding:10px 28px;">
                {html.escape(section_name)}
              </td>
            </tr>
            """.rstrip()
        )

        for row_num, row in items:
            title    = (row.get("Title") or "").strip()
            body_raw = (row.get("Body")  or "").strip()
            image    = (row.get("Image") or "").strip()

            if not title:
                print(
                    f"  [WARN] Row {row_num}: field 'Title' is empty. "
                    "Fix: enter a title. Item skipped.",
                    file=sys.stderr,
                )
                continue

            row_class = "row-white" if alternating_index % 2 == 0 else "row-alt"
            alternating_index += 1

            body_html  = render_body(body_raw)
            image_html = build_image_html(image, title)
            item_anchor = item_anchor_map.get((section_name, row_num), "")

            section_blocks.append(
                render_entry_row(
                    title=title,
                    body_html=body_html,
                    image_html=image_html,
                    row_class=row_class,
                    item_anchor=item_anchor,
                )
            )

    full_html = build_full_html(
        issue_date=issue_date,
        toc_html=toc_html,
        section_blocks=section_blocks,
        top_callout=top_callout or DEFAULT_TOP_CALLOUT,
        bottom_callout=bottom_callout or DEFAULT_BOTTOM_CALLOUT,
    )

    final_output = PROJ_DIR / "chucks_bulletin_final_output.html"

    try:
        final_output.write_text(full_html, encoding="utf-8")
        print(f"  [OK] Bulletin HTML written: {final_output}")
    except Exception as exc:
        print(f"ERROR writing output: {exc}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile events HTML output.")
    parser.add_argument("--issue-date", required=True, help="Issue date YYYY-MM-DD")
    parser.add_argument(
        "--callout",
        default=None,
        help="Optional top callout box text. If omitted, the top callout block is suppressed entirely.",
    )
    parser.add_argument(
        "--bottom-callout",
        default=None,
        help="Optional bottom callout box text override.",
    )
    args = parser.parse_args()
    sys.exit(
        compile_events(
            issue_date=args.issue_date,
            callout=args.callout,
            bottom_callout=args.bottom_callout,
        )
    )
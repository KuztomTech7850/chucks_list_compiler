"""
bulletins/compile_bulletin.py
Role: Compile bulletins_data.csv → chucks_bulletin_final_output.html
Pipeline stage: COMPILE (runs after preprocess_bulletin_text.py)
Called by: Chucks_List_Builder.py via subprocess

Key design decisions:
- HTML escaping happens BEFORE any linkification (escape-then-link, never reverse).
- URL/email matching is bounded: no trailing punctuation swallowed.
- Paragraph blocks are explicit <p> elements, not <br> chains.
- Anchor IDs are deterministic and collision-protected.
- Color palette: Montezuma County / Mesa Verde tones.
- Font sizing: elderly-accessible (18px body minimum).
"""

import csv
import html
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJ_DIR   = SCRIPT_DIR.parent
INPUT_CSV  = SCRIPT_DIR / "bulletins_data.csv"
OUTPUT_DIR = PROJ_DIR / "ChucksBulletin"
OUTPUT_HTML = SCRIPT_DIR / "chucks_bulletin_final_output.html"

# ---------------------------------------------------------------------------
# Canonical section order (must match preprocess contract)
# ---------------------------------------------------------------------------
SECTION_ORDER = [
    "Urgent Bulletins",
    "Housing Opportunities",
    "Swap Market",
    "Local Services & Help",
    "Community Announcements",
]

# ---------------------------------------------------------------------------
# Color palette: Montezuma County / Mesa Verde, Colorado
# Dusty canyon red, sage green, sandstone, deep sky, warm cream
# ---------------------------------------------------------------------------
PALETTE = {
    "bg":           "#FAF6F0",   # warm cream parchment
    "surface":      "#F2EDE4",   # sandstone
    "border":       "#C8B89A",   # weathered adobe
    "header_bg":    "#5C3D1E",   # dark canyon brown
    "header_text":  "#FAF6F0",
    "section_bg":   "#6B4C2A",   # medium canyon brown
    "section_text": "#FAF6F0",
    "accent":       "#8B6914",   # mesa gold
    "body_text":    "#2C1E0F",   # deep earth
    "muted":        "#6E5740",   # warm mid-tone
    "link":         "#1A4D6E",   # deep sky blue — strong contrast on cream
    "link_hover":   "#0D2E43",
    "urgent_bg":    "#7A1F1F",   # deep red for urgent
    "urgent_text":  "#FAF6F0",
    "toc_bg":       "#EDE5D8",
    "hr":           "#C8B89A",
}

# ---------------------------------------------------------------------------
# Zoho-safe link generation
# ---------------------------------------------------------------------------

# URL pattern: bounded — stops at whitespace and does not swallow trailing
# punctuation characters that commonly follow URLs in plain text.
_URL_RE = re.compile(
    r'(?<!\w)'                         # not preceded by word char (no mid-word match)
    r'(https?://[^\s<>"\']{4,}?)'      # scheme + body
    r'(?=[.,;:!?)}\]]*(?:\s|$))',      # stop before trailing punctuation+space or end
    re.IGNORECASE,
)

# Email pattern: bounded similarly.
_EMAIL_RE = re.compile(
    r'(?<!\w)'
    r'([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})'
    r'(?=[.,;:!?)}\]]*(?:\s|$))',
)

# Tokenizer: split text on URLs and emails so we process non-link text
# independently and never double-linkify or corrupt already-escaped content.
_TOKEN_RE = re.compile(
    r'(https?://[^\s<>"\']{4,}?(?=[.,;:!?)}\]]*(?:\s|$))'
    r'|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?=[.,;:!?)}\]]*(?:\s|$)))',
    re.IGNORECASE,
)


def linkify_escaped(escaped_text: str) -> str:
    """
    Linkify text that has ALREADY been HTML-escaped.
    Strategy: tokenize on URLs/emails, wrap each in a clean <a> tag.
    Visible text is the URL/email itself (readable, no raw crud).
    Generated links are structurally clean for Zoho tracking rewrite.
    """
    parts = _TOKEN_RE.split(escaped_text)
    out = []
    for part in parts:
        if _URL_RE.fullmatch(part.rstrip('.,;:!?)}\]')) or _URL_RE.match(part):
            clean = part.rstrip('.,;:!?)}\]')
            trailing = part[len(clean):]
            out.append(
                f'<a href="{clean}" target="_blank" rel="noopener noreferrer">'
                f'{clean}</a>{trailing}'
            )
        elif _EMAIL_RE.fullmatch(part.rstrip('.,;:!?)}\]')) or _EMAIL_RE.match(part):
            clean = part.rstrip('.,;:!?)}\]')
            trailing = part[len(clean):]
            out.append(
                f'<a href="mailto:{clean}">{clean}</a>{trailing}'
            )
        else:
            out.append(part)
    return "".join(out)


# ---------------------------------------------------------------------------
# Text → HTML body rendering
# ---------------------------------------------------------------------------

def render_body(raw_text: str) -> str:
    """
    Convert poster/plain-text body to structured, accessible HTML.
    Rules:
      - Normalize line endings to \\n.
      - Double-newline = block boundary → separate <p>.
      - Lines starting with - or * = list items → wrapped in <ul><li>.
      - Lines starting with ## = subheading → <h4>.
      - Single newline within a block = <br> (intentional line break within paragraph).
      - HTML-escape content FIRST, then linkify.
      - No raw <br> chains as primary structure.
    """
    if not raw_text:
        return ""

    # Normalize line endings
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    # Split into blocks on double newline
    blocks = re.split(r"\n{2,}", text.strip())

    out_parts = []
    list_buffer = []

    def flush_list():
        if list_buffer:
            items = "".join(
                f'<li style="margin-bottom:6px;">{item}</li>'
                for item in list_buffer
            )
            out_parts.append(
                f'<ul style="margin:0 0 14px 0;padding-left:22px;">{items}</ul>'
            )
            list_buffer.clear()

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue

        # Check if this block is a list block (majority of lines are list items)
        list_lines = [l for l in lines if re.match(r'^[\-\*•]\s', l)]
        head_lines = [l for l in lines if l.startswith("##")]

        if head_lines and len(head_lines) == len(lines):
            flush_list()
            for hl in head_lines:
                heading_text = hl.lstrip("#").strip()
                esc = html.escape(heading_text)
                linked = linkify_escaped(esc)
                out_parts.append(
                    f'<h4 style="font-size:17px;font-weight:700;'
                    f'color:{PALETTE["accent"]};margin:18px 0 6px 0;'
                    f'font-family:Georgia,serif;">{linked}</h4>'
                )
        elif list_lines:
            flush_list()
            for ll in lines:
                clean = re.sub(r'^[\-\*•]\s*', '', ll).strip()
                esc = html.escape(clean)
                linked = linkify_escaped(esc)
                list_buffer.append(linked)
            flush_list()
        else:
            flush_list()
            # Render as paragraph; single newlines within block → <br>
            inner_lines = []
            for ll in lines:
                esc = html.escape(ll)
                linked = linkify_escaped(esc)
                inner_lines.append(linked)
            inner_html = "<br>\n".join(inner_lines)
            out_parts.append(
                f'<p style="margin:0 0 14px 0;line-height:1.7;">{inner_html}</p>'
            )

    flush_list()
    return "\n".join(out_parts)


# ---------------------------------------------------------------------------
# Anchor generation (deterministic, collision-safe)
# ---------------------------------------------------------------------------

def make_anchor(title: str, seen: dict) -> str:
    """
    Generate a slug anchor ID. Collision-protected: appends -2, -3, etc.
    """
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    slug = slug[:60] or "item"
    base = slug
    n = seen.get(base, 0) + 1
    seen[base] = n
    return base if n == 1 else f"{base}-{n}"


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

EMAIL_CSS = f"""
  body {{
    margin:0; padding:0; background:{PALETTE['bg']};
    font-family:Georgia,'Times New Roman',serif;
  }}
  .wrapper {{
    max-width:660px; margin:0 auto; background:{PALETTE['bg']};
  }}
  .header {{
    background:{PALETTE['header_bg']}; color:{PALETTE['header_text']};
    padding:28px 32px 20px 32px; text-align:center;
  }}
  .header h1 {{
    margin:0 0 4px 0; font-size:28px; font-weight:700; letter-spacing:0.5px;
  }}
  .header .issue-date {{
    font-size:15px; opacity:0.85; margin:0;
  }}
  .toc-box {{
    background:{PALETTE['toc_bg']}; border:1px solid {PALETTE['border']};
    padding:18px 24px; margin:0;
  }}
  .toc-box h2 {{
    font-size:17px; font-weight:700; margin:0 0 12px 0;
    color:{PALETTE['body_text']};
  }}
  .toc-box ul {{
    margin:0; padding-left:18px;
  }}
  .toc-box li {{
    margin-bottom:6px;
  }}
  .toc-box a {{
    color:{PALETTE['link']}; text-decoration:none; font-size:16px;
  }}
  .section-header {{
    background:{PALETTE['section_bg']}; color:{PALETTE['section_text']};
    padding:12px 24px; margin:0;
    font-size:19px; font-weight:700; letter-spacing:0.3px;
  }}
  .item-block {{
    background:{PALETTE['surface']}; border-bottom:1px solid {PALETTE['border']};
    padding:20px 28px 16px 28px;
  }}
  .item-block.urgent {{
    background:{PALETTE['urgent_bg']}; color:{PALETTE['urgent_text']};
    border-color:{PALETTE['urgent_bg']};
  }}
  .item-title {{
    font-size:20px; font-weight:700; margin:0 0 6px 0;
    color:{PALETTE['body_text']};
  }}
  .item-block.urgent .item-title {{ color:{PALETTE['urgent_text']}; }}
  .item-meta {{
    font-size:14px; color:{PALETTE['muted']}; margin:0 0 12px 0;
  }}
  .item-block.urgent .item-meta {{ color:#E8D5C0; }}
  .item-body {{
    font-size:18px; line-height:1.75; color:{PALETTE['body_text']};
  }}
  .item-block.urgent .item-body {{ color:{PALETTE['urgent_text']}; }}
  .item-body a {{
    color:{PALETTE['link']}; text-decoration:underline;
  }}
  .item-block.urgent .item-body a {{ color:#A8D4F0; }}
  .item-image {{
    margin:12px 0 0 0; text-align:center;
  }}
  .item-image img {{
    max-width:100%; height:auto; border-radius:4px;
    border:1px solid {PALETTE['border']};
  }}
  .footer {{
    background:{PALETTE['header_bg']}; color:{PALETTE['header_text']};
    padding:18px 32px; text-align:center; font-size:14px;
  }}
  hr.section-rule {{
    border:none; border-top:2px solid {PALETTE['hr']}; margin:0;
  }}
"""


def build_image_html(image_path: str, title: str, images_dir: Path) -> str:
    """
    Return clickable image HTML if the image file is found, else empty string.
    Logs a warning (not a fatal error) if missing.
    """
    if not image_path or not image_path.strip():
        return ""
    img_file = images_dir / image_path.strip()
    if not img_file.exists():
        print(
            f"  [WARN] Image not found: {img_file} "
            f"(referenced by item '{title}'). Skipping image.",
            file=sys.stderr,
        )
        return ""
    alt = html.escape(title)
    src = image_path.strip()
    return (
        f'<div class="item-image">'
        f'<a href="../Images/{src}" target="_blank">'
        f'<img src="../Images/{src}" alt="{alt}" width="580" style="max-width:100%;">'
        f'</a></div>'
    )


# ---------------------------------------------------------------------------
# Main compile function
# ---------------------------------------------------------------------------

def compile_bulletins(issue_date: str) -> int:
    """
    Read bulletins_data.csv, render HTML, write output.
    Returns 0 on success, 1 on error.
    """
    images_dir = PROJ_DIR / "Images"

    # -- Read CSV --
    rows = []
    if not INPUT_CSV.exists():
        print(f"ERROR: Input CSV not found: {INPUT_CSV}", file=sys.stderr)
        return 1
    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {"Title", "Body", "Section", "Received", "Expires"}
            if reader.fieldnames is None:
                print("ERROR: bulletins_data.csv appears empty or has no header row.", file=sys.stderr)
                return 1
            actual_cols = set(reader.fieldnames)
            missing = required_cols - actual_cols
            if missing:
                print(
                    f"ERROR: bulletins_data.csv is missing required columns: "
                    f"{', '.join(sorted(missing))}\n"
                    f"  Found columns: {', '.join(sorted(actual_cols))}\n"
                    f"  Fix: Re-export from Chucks-list-MASTER.ods ensuring all "
                    f"required columns are present.",
                    file=sys.stderr,
                )
                return 1
            for i, row in enumerate(reader, start=2):  # row 2 = first data row
                rows.append((i, row))
    except Exception as e:
        print(f"ERROR reading {INPUT_CSV}: {e}", file=sys.stderr)
        return 1

    # -- Group by section, maintaining canonical order --
    sections: dict[str, list] = defaultdict(list)
    for row_num, row in rows:
        section = (row.get("Section") or "").strip()
        if not section:
            print(
                f"  [WARN] Row {row_num}: empty Section field, "
                f"item '{row.get('Title', '(no title)')}' skipped.",
                file=sys.stderr,
            )
            continue
        if section not in SECTION_ORDER:
            print(
                f"  [WARN] Row {row_num}: unknown section '{section}' "
                f"for item '{row.get('Title', '(no title)')}'. "
                f"Valid sections: {', '.join(SECTION_ORDER)}. Item skipped.",
                file=sys.stderr,
            )
            continue
        sections[section].append((row_num, row))

    # -- Build TOC entries and item blocks --
    toc_entries = []   # list of (anchor, label)
    body_blocks = []   # list of HTML strings
    seen_anchors: dict = {}

    for section in SECTION_ORDER:
        items = sections.get(section, [])
        if not items:
            continue

        section_anchor = make_anchor("section-" + section, seen_anchors)
        toc_entries.append((section_anchor, f"▸ {section}"))
        body_blocks.append(
            f'<a name="{section_anchor}"></a>'
            f'<div class="section-header">{html.escape(section)}</div>'
        )

        is_urgent = section == "Urgent Bulletins"

        for row_num, row in items:
            title    = (row.get("Title") or "").strip()
            body_raw = (row.get("Body") or "").strip()
            contact  = (row.get("Contact") or "").strip()
            phone    = (row.get("Phone") or "").strip()
            image    = (row.get("Image") or "").strip()
            received = (row.get("Received") or "").strip()
            expires  = (row.get("Expires") or "").strip()

            if not title:
                print(
                    f"  [WARN] Row {row_num}: item has empty Title. Skipping.",
                    file=sys.stderr,
                )
                continue

            item_anchor = make_anchor(title, seen_anchors)
            toc_entries.append((item_anchor, f"\u00a0\u00a0\u00a0\u00a0{title}"))

            meta_parts = []
            if received:
                meta_parts.append(f"Received: {html.escape(received)}")
            if expires:
                meta_parts.append(f"Expires: {html.escape(expires)}")
            if contact:
                meta_parts.append(f"Contact: {html.escape(contact)}")
            if phone:
                meta_parts.append(f"Phone: {html.escape(phone)}")
            meta_html = " &nbsp;|&nbsp; ".join(meta_parts)

            body_html  = render_body(body_raw)
            image_html = build_image_html(image, title, images_dir)

            urgent_class = " urgent" if is_urgent else ""
            body_blocks.append(
                f'<a name="{item_anchor}"></a>'
                f'<div class="item-block{urgent_class}">'
                f'  <div class="item-title">{html.escape(title)}</div>'
                f'  <div class="item-meta">{meta_html}</div>'
                f'  <div class="item-body">{body_html}</div>'
                f'  {image_html}'
                f'</div>'
            )

        body_blocks.append('<hr class="section-rule">')

    # -- Build TOC HTML --
    toc_li = "\n".join(
        f'<li><a href="#{anchor}">{html.escape(label)}</a></li>'
        for anchor, label in toc_entries
    )
    toc_html = (
        f'<div class="toc-box">'
        f'<h2>In This Issue</h2>'
        f'<ul style="list-style:none;padding-left:0;">{toc_li}</ul>'
        f'</div>'
    )

    # -- Assemble full HTML --
    body_content = "\n".join(body_blocks)
    full_html = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Chuck's List Bulletin — {html.escape(issue_date)}</title>
      <style>
    {EMAIL_CSS}
      </style>
    </head>
    <body>
    <div class="wrapper">
      <div class="header">
        <h1>Chuck's List Bulletin</h1>
        <p class="issue-date">Issue Date: {html.escape(issue_date)}</p>
      </div>
      {toc_html}
      {body_content}
      <div class="footer">
        &copy; Chuck's List &mdash; Montezuma County, Colorado
      </div>
    </div>
    </body>
    </html>
    """)

    # -- Write output --
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        OUTPUT_HTML.write_text(full_html, encoding="utf-8")
        # Also write to staging folder
        staging_copy = OUTPUT_DIR / "chucks_bulletin_final_output.html"
        staging_copy.write_text(full_html, encoding="utf-8")
        print(f"  [OK] Bulletin HTML written: {OUTPUT_HTML}")
        print(f"  [OK] Bulletin staging copy: {staging_copy}")
    except Exception as e:
        print(f"ERROR writing output: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Compile bulletin HTML output.")
    p.add_argument("--issue-date", required=True, help="Issue date YYYY-MM-DD")
    args = p.parse_args()
    sys.exit(compile_bulletins(args.issue_date))
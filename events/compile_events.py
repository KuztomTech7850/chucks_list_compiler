"""
events/compile_events.py
Role: Compile events_data.csv → chucks_events_final_output.html
Pipeline stage: COMPILE (runs after preprocess_events_text.py)
Called by: Chucks_List_Builder.py via subprocess

Design decisions: same as compile_bulletin.py.
Event-specific: date range display, location field, event anchor/TOC by date+title.
"""

import csv
import html
import re
import sys
import textwrap
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
PROJ_DIR    = SCRIPT_DIR.parent
INPUT_CSV   = SCRIPT_DIR / "events_data.csv"
OUTPUT_DIR  = PROJ_DIR / "ChucksEvents"
OUTPUT_HTML = SCRIPT_DIR / "chucks_events_final_output.html"

# Reuse palette and link logic from compile_bulletin.py inline
# (kept here for self-contained module — no cross-module import needed)
PALETTE = {
    "bg":           "#FAF6F0",
    "surface":      "#F2EDE4",
    "border":       "#C8B89A",
    "header_bg":    "#2D5A3D",   # deep sage green for events (distinguishes from bulletin)
    "header_text":  "#FAF6F0",
    "section_bg":   "#3D7A52",
    "section_text": "#FAF6F0",
    "accent":       "#8B6914",
    "body_text":    "#2C1E0F",
    "muted":        "#6E5740",
    "link":         "#1A4D6E",
    "toc_bg":       "#EDE5D8",
    "hr":           "#C8B89A",
}

EMAIL_CSS = f"""
  body {{ margin:0; padding:0; background:{PALETTE['bg']};
    font-family:Georgia,'Times New Roman',serif; }}
  .wrapper {{ max-width:660px; margin:0 auto; background:{PALETTE['bg']}; }}
  .header {{ background:{PALETTE['header_bg']}; color:{PALETTE['header_text']};
    padding:28px 32px 20px 32px; text-align:center; }}
  .header h1 {{ margin:0 0 4px 0; font-size:28px; font-weight:700; letter-spacing:0.5px; }}
  .header .issue-date {{ font-size:15px; opacity:0.85; margin:0; }}
  .toc-box {{ background:{PALETTE['toc_bg']}; border:1px solid {PALETTE['border']};
    padding:18px 24px; margin:0; }}
  .toc-box h2 {{ font-size:17px; font-weight:700; margin:0 0 12px 0; color:{PALETTE['body_text']}; }}
  .toc-box ul {{ margin:0; padding-left:18px; }}
  .toc-box li {{ margin-bottom:6px; }}
  .toc-box a {{ color:{PALETTE['link']}; text-decoration:none; font-size:16px; }}
  .item-block {{ background:{PALETTE['surface']}; border-bottom:1px solid {PALETTE['border']};
    padding:20px 28px 16px 28px; }}
  .item-title {{ font-size:20px; font-weight:700; margin:0 0 6px 0; color:{PALETTE['body_text']}; }}
  .item-meta {{ font-size:14px; color:{PALETTE['muted']}; margin:0 0 12px 0; }}
  .item-body {{ font-size:18px; line-height:1.75; color:{PALETTE['body_text']}; }}
  .item-body a {{ color:{PALETTE['link']}; text-decoration:underline; }}
  .item-image {{ margin:12px 0 0 0; text-align:center; }}
  .item-image img {{ max-width:100%; height:auto; border-radius:4px;
    border:1px solid {PALETTE['border']}; }}
  .footer {{ background:{PALETTE['header_bg']}; color:{PALETTE['header_text']};
    padding:18px 32px; text-align:center; font-size:14px; }}
  hr.section-rule {{ border:none; border-top:2px solid {PALETTE['hr']}; margin:0; }}
"""

_TOKEN_RE = re.compile(
    r'(https?://[^\s<>"\']{4,}?(?=[.,;:!?)}\]]*(?:\s|$))'
    r'|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?=[.,;:!?)}\]]*(?:\s|$)))',
    re.IGNORECASE,
)
_URL_RE   = re.compile(r'^https?://', re.IGNORECASE)
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def linkify_escaped(escaped_text: str) -> str:
    parts = _TOKEN_RE.split(escaped_text)
    out = []
    for part in parts:
        clean = part.rstrip('.,;:!?)}\]')
        trailing = part[len(clean):]
        if _URL_RE.match(clean):
            out.append(
                f'<a href="{clean}" target="_blank" rel="noopener noreferrer">'
                f'{clean}</a>{trailing}'
            )
        elif _EMAIL_RE.match(clean):
            out.append(f'<a href="mailto:{clean}">{clean}</a>{trailing}')
        else:
            out.append(part)
    return "".join(out)


def render_body(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", text.strip())
    out_parts = []
    list_buffer = []

    def flush_list():
        if list_buffer:
            items = "".join(
                f'<li style="margin-bottom:6px;">{item}</li>' for item in list_buffer
            )
            out_parts.append(
                f'<ul style="margin:0 0 14px 0;padding-left:22px;">{items}</ul>'
            )
            list_buffer.clear()

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue
        list_lines = [l for l in lines if re.match(r'^[\-\*•]\s', l)]
        head_lines = [l for l in lines if l.startswith("##")]
        if head_lines and len(head_lines) == len(lines):
            flush_list()
            for hl in head_lines:
                heading_text = hl.lstrip("#").strip()
                out_parts.append(
                    f'<h4 style="font-size:17px;font-weight:700;'
                    f'color:{PALETTE["accent"]};margin:18px 0 6px 0;">'
                    f'{linkify_escaped(html.escape(heading_text))}</h4>'
                )
        elif list_lines:
            flush_list()
            for ll in lines:
                clean = re.sub(r'^[\-\*•]\s*', '', ll).strip()
                list_buffer.append(linkify_escaped(html.escape(clean)))
            flush_list()
        else:
            flush_list()
            inner = "<br>\n".join(
                linkify_escaped(html.escape(ll)) for ll in lines
            )
            out_parts.append(
                f'<p style="margin:0 0 14px 0;line-height:1.7;">{inner}</p>'
            )
    flush_list()
    return "\n".join(out_parts)


def make_anchor(title: str, seen: dict) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")[:60] or "item"
    n = seen.get(slug, 0) + 1
    seen[slug] = n
    return slug if n == 1 else f"{slug}-{n}"


def build_image_html(image_path: str, title: str, images_dir: Path) -> str:
    if not image_path or not image_path.strip():
        return ""
    img_file = images_dir / image_path.strip()
    if not img_file.exists():
        print(
            f"  [WARN] Image not found: {img_file} "
            f"(item '{title}'). Skipping image.",
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


def compile_events(issue_date: str) -> int:
    images_dir = PROJ_DIR / "Images"

    if not INPUT_CSV.exists():
        print(f"ERROR: Input CSV not found: {INPUT_CSV}", file=sys.stderr)
        return 1

    rows = []
    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print("ERROR: events_data.csv appears empty or has no header row.", file=sys.stderr)
                return 1
            required_cols = {"Title", "Body", "Starts", "Ends"}
            actual_cols = set(reader.fieldnames)
            missing = required_cols - actual_cols
            if missing:
                print(
                    f"ERROR: events_data.csv is missing required columns: "
                    f"{', '.join(sorted(missing))}\n"
                    f"  Found columns: {', '.join(sorted(actual_cols))}\n"
                    f"  Fix: Re-export from Chucks-list-MASTER.ods and re-run preprocess.",
                    file=sys.stderr,
                )
                return 1
            for i, row in enumerate(reader, start=2):
                rows.append((i, row))
    except Exception as e:
        print(f"ERROR reading {INPUT_CSV}: {e}", file=sys.stderr)
        return 1

    if not rows:
        print(
            f"  [WARN] events_data.csv has no data rows for issue date {issue_date}. "
            f"The output will be an empty events email.",
            file=sys.stderr,
        )

    # Sort events by start date
    def sort_key(item):
        _, r = item
        return (r.get("Starts") or "9999-99-99")

    rows.sort(key=sort_key)

    toc_entries = []
    body_blocks = []
    seen_anchors: dict = {}

    for row_num, row in rows:
        title    = (row.get("Title") or "").strip()
        body_raw = (row.get("Body") or "").strip()
        starts   = (row.get("Starts") or "").strip()
        ends     = (row.get("Ends") or "").strip()
        location = (row.get("Location") or "").strip()
        contact  = (row.get("Contact") or "").strip()
        phone    = (row.get("Phone") or "").strip()
        image    = (row.get("Image") or "").strip()

        if not title:
            print(f"  [WARN] Row {row_num}: empty Title, skipping.", file=sys.stderr)
            continue

        anchor = make_anchor(title, seen_anchors)
        toc_label = title if not starts else f"{title} ({starts})"
        toc_entries.append((anchor, toc_label))

        meta_parts = []
        if starts and ends and starts != ends:
            meta_parts.append(f"Dates: {html.escape(starts)} – {html.escape(ends)}")
        elif starts:
            meta_parts.append(f"Date: {html.escape(starts)}")
        if location:
            meta_parts.append(f"Location: {html.escape(location)}")
        if contact:
            meta_parts.append(f"Contact: {html.escape(contact)}")
        if phone:
            meta_parts.append(f"Phone: {html.escape(phone)}")
        meta_html = " &nbsp;|&nbsp; ".join(meta_parts)

        body_html  = render_body(body_raw)
        image_html = build_image_html(image, title, images_dir)

        body_blocks.append(
            f'<a name="{anchor}"></a>'
            f'<div class="item-block">'
            f'  <div class="item-title">{html.escape(title)}</div>'
            f'  <div class="item-meta">{meta_html}</div>'
            f'  <div class="item-body">{body_html}</div>'
            f'  {image_html}'
            f'</div>'
            f'<hr class="section-rule">'
        )

    toc_li = "\n".join(
        f'<li><a href="#{anchor}">{html.escape(label)}</a></li>'
        for anchor, label in toc_entries
    )
    toc_html = (
        f'<div class="toc-box">'
        f'<h2>Upcoming Events</h2>'
        f'<ul style="list-style:none;padding-left:0;">{toc_li}</ul>'
        f'</div>'
    )

    full_html = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Chuck's List Events — {html.escape(issue_date)}</title>
      <style>
    {EMAIL_CSS}
      </style>
    </head>
    <body>
    <div class="wrapper">
      <div class="header">
        <h1>Chuck's List Events</h1>
        <p class="issue-date">Issue Date: {html.escape(issue_date)}</p>
      </div>
      {toc_html}
      {"".join(body_blocks) if body_blocks else '<div style="padding:28px;text-align:center;color:#6E5740;">No events scheduled for this period.</div>'}
      <div class="footer">
        &copy; Chuck's List &mdash; Montezuma County, Colorado
      </div>
    </div>
    </body>
    </html>
    """)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        OUTPUT_HTML.write_text(full_html, encoding="utf-8")
        staging_copy = OUTPUT_DIR / "chucks_events_final_output.html"
        staging_copy.write_text(full_html, encoding="utf-8")
        print(f"  [OK] Events HTML written: {OUTPUT_HTML}")
        print(f"  [OK] Events staging copy: {staging_copy}")
    except Exception as e:
        print(f"ERROR writing output: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Compile events HTML output.")
    p.add_argument("--issue-date", required=True, help="Issue date YYYY-MM-DD")
    args = p.parse_args()
    sys.exit(compile_events(args.issue_date))
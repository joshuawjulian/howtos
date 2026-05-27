#!/usr/bin/env python3
"""Build printer-friendly PDFs of every how-to in this repo.

Usage:
    uv run --with markdown --with weasyprint --with pygments \
        scripts/build-pdfs.py

Optimized for:
- Reading on paper (B&W printer, regular letter-size).
- Dense layout to save paper without sacrificing readability.
- Subtle admonition / code block styling (no big colored boxes).
- Sensible page breaks (no orphan headings).

Pre-processes:
- GFM admonitions ([!NOTE], [!WARNING], etc.) -> styled blockquotes
  with a bold label.
- Mermaid code blocks -> a placeholder note pointing to the online
  version (Mermaid is a browser-side library; can't render in PDF
  without a heavyweight Chromium dependency).

Output: pdfs/<topic>.pdf for each how-to subdirectory.
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown
from weasyprint import HTML, CSS

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs"
PDF_DIR.mkdir(exist_ok=True)

HOWTOS = [
    d
    for d in sorted(ROOT.iterdir())
    if d.is_dir()
    and (d / "README.md").exists()
    and d.name not in {"pdfs", "scripts", ".git", ".github"}
]


ADMONITION_LABELS = {
    "NOTE":      "NOTE",
    "TIP":       "TIP",
    "IMPORTANT": "IMPORTANT",
    "WARNING":   "WARNING",
    "CAUTION":   "CAUTION",
}


def preprocess_admonitions(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        kind = match.group("kind").upper()
        body = match.group("body")
        label = ADMONITION_LABELS.get(kind, kind.title())
        return f"> **{label}.** " + body.lstrip().removeprefix("> ")

    pattern = re.compile(
        r"^> \[!(?P<kind>NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\n"
        r"(?P<body>(?:> .*(?:\n|$))+)",
        re.MULTILINE,
    )
    return pattern.sub(replace, text)


def preprocess_mermaid(text: str) -> str:
    """Replace ```mermaid blocks with a tasteful placeholder."""

    def replace(_match: re.Match[str]) -> str:
        return (
            "> *[Diagram: see the online version on GitHub for the "
            "interactive flowchart.]*\n"
        )

    pattern = re.compile(r"^```mermaid\n.*?\n```\s*$", re.MULTILINE | re.DOTALL)
    return pattern.sub(replace, text)


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    raw = md_path.read_text()
    processed = preprocess_admonitions(raw)
    processed = preprocess_mermaid(processed)

    html_body = markdown.markdown(
        processed,
        extensions=[
            "extra",
            "toc",
            "tables",
            "fenced_code",
            "sane_lists",
            "codehilite",
        ],
        extension_configs={
            "toc": {"toc_depth": "2-3"},
            "codehilite": {"css_class": "highlight", "guess_lang": False, "noclasses": False},
        },
    )

    title = md_path.parent.name.replace("-", " ").title()
    subtitle = "howtos · joshuawjulian/howtos"
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
</head>
<body>
<div class="meta">{subtitle}</div>
{html_body}
</body>
</html>"""

    HTML(string=full_html, base_url=str(md_path.parent)).write_pdf(
        str(pdf_path),
        stylesheets=[CSS(string=PRINT_CSS)],
    )


# Print-optimized stylesheet:
#  - serif body font (more legible than sans on paper for long reads)
#  - no colored backgrounds (toner-friendly)
#  - subtle borders for code + admonitions
#  - tight but readable line height
#  - page-break controls so headings don't orphan
PRINT_CSS = r"""
@page {
  size: letter;
  margin: 0.7in 0.7in 0.85in 0.7in;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: "Charter", "Georgia", "Source Serif Pro", serif;
    font-size: 9pt;
    color: #555;
  }
  @bottom-right {
    content: string(doctitle);
    font-family: "Charter", "Georgia", "Source Serif Pro", serif;
    font-size: 8.5pt;
    color: #555;
    font-style: italic;
  }
}

body {
  font-family: "Charter", "Georgia", "Source Serif Pro", "Iowan Old Style", serif;
  font-size: 10pt;
  line-height: 1.42;
  color: #111;
}

.meta {
  font-family: -apple-system, "Helvetica Neue", sans-serif;
  font-size: 8.5pt;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.4em;
  text-align: right;
}

h1 {
  string-set: doctitle content();
  font-family: "Charter", "Georgia", serif;
  font-size: 20pt;
  font-weight: 700;
  margin: 0 0 0.5em 0;
  color: #000;
  border-bottom: 1.5pt solid #000;
  padding-bottom: 6px;
  page-break-after: avoid;
}

h2 {
  font-family: "Charter", "Georgia", serif;
  font-size: 14pt;
  font-weight: 700;
  margin: 1.5em 0 0.4em 0;
  color: #000;
  border-bottom: 0.5pt solid #888;
  padding-bottom: 3px;
  page-break-after: avoid;
  page-break-before: auto;
}

h3 {
  font-family: "Charter", "Georgia", serif;
  font-size: 11.5pt;
  font-weight: 700;
  margin: 1.1em 0 0.3em 0;
  color: #111;
  page-break-after: avoid;
}

h4 {
  font-family: "Charter", "Georgia", serif;
  font-size: 10.5pt;
  font-weight: 700;
  margin: 0.9em 0 0.25em 0;
  page-break-after: avoid;
}

p, ul, ol { margin: 0.35em 0; }

p { orphans: 3; widows: 3; }

strong { color: #000; font-weight: 700; }
em { color: #333; }

ul, ol { padding-left: 1.4em; }
li { margin: 0.12em 0; }

a {
  color: #000;
  text-decoration: none;
  border-bottom: 0.3pt solid #888;
}

img {
  max-width: 100%;
  max-height: 4in;
  display: block;
  margin: 0.5em auto;
  page-break-inside: avoid;
}

table {
  border-collapse: collapse;
  margin: 0.55em 0;
  width: 100%;
  font-size: 9pt;
  page-break-inside: avoid;
}

th, td {
  border: 0.5pt solid #888;
  padding: 3.5px 6px;
  text-align: left;
  vertical-align: top;
}

th {
  background: transparent;
  font-weight: 700;
  border-bottom: 1pt solid #000;
}

hr {
  border: none;
  border-top: 0.5pt solid #888;
  margin: 1.2em 0;
}

/* Inline code */
code {
  font-family: "Source Code Pro", "Consolas", "DejaVu Sans Mono", monospace;
  background: transparent;
  font-size: 9pt;
  border: 0.4pt solid #aaa;
  padding: 0 3px;
  border-radius: 2px;
}

/* Fenced code blocks */
pre {
  background: transparent;
  border: 0.5pt solid #888;
  padding: 7px 10px;
  border-radius: 0;
  overflow-x: hidden;
  font-size: 8.5pt;
  line-height: 1.35;
  page-break-inside: avoid;
  white-space: pre-wrap;
  word-wrap: break-word;
}
pre code {
  background: transparent;
  padding: 0;
  border: 0;
  font-size: inherit;
}

/* Blockquotes (used for admonitions) */
blockquote {
  border-left: 2pt solid #555;
  background: transparent;
  margin: 0.6em 0;
  padding: 0.15em 0.7em;
  page-break-inside: avoid;
  font-style: italic;
  color: #222;
}

blockquote strong {
  font-style: normal;
  color: #000;
  text-transform: uppercase;
  font-size: 8.5pt;
  letter-spacing: 0.06em;
}

blockquote p { margin: 0.2em 0; }
blockquote p:first-child { margin-top: 0; }
blockquote p:last-child { margin-bottom: 0; }

/* Avoid splitting these */
table, pre, blockquote, img, h1, h2, h3, h4 {
  page-break-inside: avoid;
}

h2 + p, h3 + p, h4 + p,
h2 + ul, h3 + ul, h4 + ul,
h2 + pre, h3 + pre, h4 + pre {
  page-break-before: avoid;
}

/* Syntax highlighting via pygments — tone down for B&W printing */
.highlight .k, .highlight .kn, .highlight .kd, .highlight .kr { font-weight: 700; }
.highlight .s, .highlight .s1, .highlight .s2 { font-style: italic; }
.highlight .c, .highlight .c1, .highlight .cm { color: #666; font-style: italic; }
.highlight .nb, .highlight .nf { font-weight: 600; }
"""


def main() -> None:
    print(f"==> Building printer-friendly PDFs for {len(HOWTOS)} how-tos...")
    for ht in HOWTOS:
        out = PDF_DIR / f"{ht.name}.pdf"
        md_to_pdf(ht / "README.md", out)
        size_kb = out.stat().st_size / 1024
        print(f"  ✓ {ht.name}.pdf ({size_kb:,.0f} KB)")
    print(f"==> Done. PDFs in {PDF_DIR}/")


if __name__ == "__main__":
    main()

"""Build docs/Atrium-Product-Blueprint.pdf from the Markdown source.

Pipeline: Markdown -> HTML (python-markdown, mermaid fences replaced by the SVGs
in docs/diagrams) -> PDF (headless Chrome) -> PyMuPDF post-pass (footer with page
numbers, bookmarks, table of contents with page numbers via a second render).

Usage:  python tools/render_diagrams.py && python tools/build_pdf.py
"""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import markdown

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "docs" / "Atrium-Product-Blueprint.md"
PDF_PATH = ROOT / "docs" / "Atrium-Product-Blueprint.pdf"
DIAGRAM_DIR = ROOT / "docs" / "diagrams"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

DOC_TITLE = "Atrium — Product Blueprint"
DOC_SUB = "AI-native wealth operating system: from first lead to settled trade"
FOOTER_LEFT = "Atrium — Product Blueprint · v0.1 · 11 October 2026 · Team Ctrl+Alt+Hiru"

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
:root {
  --ink: #1b2430; --muted: #5b6774; --line: #d9dee5; --accent: #0b5fff;
  --accent-soft: #e8f0ff; --head-bg: #f3f5f8; --warn: #b45309;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: "Segoe UI", Inter, Arial, sans-serif; color: var(--ink);
       font-size: 10.4pt; line-height: 1.48; }
h1, h2, h3, h4 { font-weight: 650; line-height: 1.22; color: var(--ink); }
h1 { font-size: 24pt; margin: 0 0 6pt; }
h2 { font-size: 16.5pt; margin: 0 0 10pt; padding-bottom: 5pt;
     border-bottom: 2px solid var(--accent); break-before: page; }
h2:first-of-type { break-before: auto; }
h3 { font-size: 12.5pt; margin: 16pt 0 6pt; color: #0b3d91; }
h4 { font-size: 11pt; margin: 12pt 0 4pt; }
h2, h3, h4 { break-after: avoid; page-break-after: avoid; }
h3 + p, h3 + table, h3 + ul, h3 + div.diagram { break-before: avoid; }
.diagram { margin: 6pt 0 14pt; padding: 8pt; border: 1px solid var(--line); border-radius: 4px;
           background: #fff; break-inside: avoid; page-break-inside: avoid; }
.diagram svg { max-height: 225mm; }
p { margin: 0 0 7pt; }
ul, ol { margin: 0 0 8pt 0; padding-left: 20pt; }
li { margin: 0 0 3pt; }
li > ul, li > ol { margin-top: 3pt; }
strong { font-weight: 650; }
a { color: var(--accent); text-decoration: none; word-break: break-all; }
hr { border: 0; border-top: 1px solid var(--line); margin: 14pt 0; }
blockquote { margin: 8pt 0 10pt; padding: 8pt 12pt; background: var(--accent-soft);
             border-left: 4px solid var(--accent); border-radius: 3px; }
blockquote p { margin: 0; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 9.2pt;
       background: #f4f6f8; padding: 0 3px; border-radius: 3px; }
pre { font-family: Consolas, "Cascadia Mono", monospace; font-size: 8.8pt;
      background: #f4f6f8; border: 1px solid var(--line); border-radius: 4px;
      padding: 8pt 10pt; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 12pt; font-size: 9.3pt;
        break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border: 1px solid var(--line); padding: 4.5pt 6pt; vertical-align: top;
         text-align: left; }
th { background: var(--head-bg); font-weight: 650; }
td:first-child { white-space: nowrap; }
table.meta td:first-child { width: 22%; font-weight: 650; background: var(--head-bg); }
pre.mermaid { background: #fff; border: 1px solid var(--line); text-align: center;
              padding: 8pt; break-inside: avoid; }
pre.mermaid svg { max-width: 100%; height: auto; max-height: 230mm; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center;
         break-after: page; }
.cover .kicker { color: var(--accent); font-weight: 650; letter-spacing: .08em;
                 text-transform: uppercase; font-size: 9.5pt; margin-bottom: 14pt; }
.cover h1 { font-size: 34pt; margin-bottom: 8pt; }
.cover .sub { font-size: 14pt; color: var(--muted); margin-bottom: 28pt; }
.cover table { width: 70%; }
.cover .note { color: var(--muted); font-size: 9pt; margin-top: 30pt; }
.toc { break-after: page; }
.toc h2 { break-before: auto; }
.toc ul { list-style: none; padding-left: 0; margin: 0; }
.toc > ul > li { margin: 0 0 5pt; font-weight: 650; }
.toc ul ul { padding-left: 16pt; font-weight: 400; margin-top: 2pt; }
.toc li { display: flex; justify-content: space-between; gap: 8pt; }
.toc li a { color: var(--ink); flex: 1; }
.toc li a::after { content: ""; }
.toc .pg { color: var(--muted); font-variant-numeric: tabular-nums; }
.toc li ul { flex-basis: 100%; }
.toc li { flex-wrap: wrap; }
.checklist li { list-style: none; }
.callout { background: #fff8e6; border-left: 4px solid var(--warn); padding: 6pt 10pt;
           margin: 8pt 0; }
"""


def strip_front_matter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def extract_headings(md_text: str) -> list[tuple[int, str, str]]:
    """Return (level, text, slug) for ## and ### headings, in order."""
    out = []
    in_fence = False
    for line in md_text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(##|###)\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            out.append((level, text, slugify(text)))
    return out


def slugify(text: str) -> str:
    # Mirror python-markdown's default slugify closely enough for our anchors.
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s).strip("-")
    return s


def md_to_body_html(md_text: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "toc"],
        extension_configs={"toc": {"slugify": lambda v, sep: slugify(v)}},
    )
    body = md.convert(md_text)
    # Mermaid fences -> pre-rendered SVGs from docs/diagrams (see tools/render_diagrams.py).
    counter = {"n": 0}

    def _mermaid(m):
        counter["n"] += 1
        svg_path = DIAGRAM_DIR / f"diagram-{counter['n']:02d}.svg"
        if not svg_path.exists():
            raise FileNotFoundError(f"{svg_path} missing; run tools/render_diagrams.py first")
        svg = svg_path.read_text(encoding="utf-8")
        svg = re.sub(r"^\s*<\?xml[^>]*\?>", "", svg)
        # Make the root scale to the column: drop fixed width/height, keep the viewBox.
        def _root(mm):
            tag = mm.group(0)
            tag = re.sub(r'\s(width|height)="[^"]*"', "", tag)
            tag = re.sub(r'\sstyle="[^"]*"', "", tag)
            return tag[:-1] + ' style="max-width:100%;height:auto;display:block;margin:0 auto">'
        svg = re.sub(r"<svg\b[^>]*>", _root, svg, count=1)
        return f'<div class="diagram">{svg}</div>'

    body = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>', _mermaid, body, flags=re.S
    )
    # Task-list checkboxes -> unicode boxes, and mark their lists so bullets are hidden.
    body = body.replace("<li>[ ] ", "<li>\u2610 ").replace("<li>[x] ", "<li>\u2611 ")
    body = re.sub(r"<ul>(\s*<li>[\u2610\u2611])", r'<ul class="checklist">\1', body)
    return body


def build_toc_html(headings, pages: dict[str, int] | None) -> str:
    parts = ['<div class="toc"><h2>Contents</h2><ul>']
    open_sub = False
    for level, text, slug in headings:
        if text.lower() in ("contents",):
            continue
        pg = ""
        if pages and slug in pages:
            pg = f'<span class="pg">{pages[slug]}</span>'
        item = f'<li><a href="#{slug}">{html.escape(text)}</a>{pg}</li>'
        if level == 2:
            if open_sub:
                parts.append("</ul></li>")
                open_sub = False
            parts.append(item[:-5])  # keep <li> open for a possible sub-list
            parts.append("<ul>")
            open_sub = True
        else:
            parts.append(item)
    if open_sub:
        parts.append("</ul></li>")
    parts.append("</ul></div>")
    out = "".join(parts)
    out = out.replace("<ul></ul></li>", "</li>")  # tidy empty sub-lists
    return out


def wrap_html(body: str, toc_html: str) -> str:
    cover = f"""
<div class="cover">
  <div class="kicker">Google Cloud AI Builder Cup 2026 · BFSI: Intelligent Risk, Fraud &amp; Financial Experiences</div>
  <h1>{html.escape(DOC_TITLE)}</h1>
  <div class="sub">{html.escape(DOC_SUB)}</div>
  <table class="meta">
    <tr><td>Team</td><td>Ctrl+Alt+Hiru</td></tr>
    <tr><td>Version</td><td>0.1 — design draft for team review</td></tr>
    <tr><td>Date</td><td>11 October 2026</td></tr>
    <tr><td>Status</td><td>Awaiting team sign-off before build starts</td></tr>
    <tr><td>Submission deadline</td><td>18 October 2026</td></tr>
  </table>
  <div class="note">Prototype design document. Projections and scores described here are illustrative. The prototype uses synthetic data and paper trading only; nothing in it is investment advice.</div>
</div>
"""
    # Drop the markdown's own title block (h1 + sub + meta table) since the cover carries it.
    body = re.sub(r"^<h1[^>]*>.*?</h1>\s*<p><strong>.*?</strong></p>\s*<table>.*?</table>\s*",
                  "", body, count=1, flags=re.S)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(DOC_TITLE)}</title>
<style>{CSS}</style>
</head><body>
{cover}
{toc_html}
{body}
</body></html>"""


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    profile = Path(tempfile.mkdtemp(prefix="chrome-pdf-"))
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
        f"--user-data-dir={profile}", "--allow-file-access-from-files",
        "--no-pdf-header-footer", "--virtual-time-budget=8000",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not pdf_path.exists() or pdf_path.stat().st_size < 10_000:
        raise RuntimeError("Chrome produced no usable PDF")


def locate_headings(pdf_path: Path, headings) -> dict[str, int]:
    """Map heading slug -> 1-based page number by searching the rendered text."""
    doc = fitz.open(pdf_path)
    pages: dict[str, int] = {}
    cursor = 2  # skip cover (page 1); TOC page(s) will be skipped by the exact-size check
    for level, text, slug in headings:
        found = None
        for pno in range(cursor, doc.page_count):
            page = doc[pno]
            hits = page.search_for(text)
            if not hits:
                continue
            # Headings are larger than body text; keep the hit whose span font size is large.
            for rect in hits:
                spans = page.get_text("dict", clip=rect)["blocks"]
                size = 0
                for b in spans:
                    for l in b.get("lines", []):
                        for s in l.get("spans", []):
                            size = max(size, s.get("size", 0))
                if size >= 12.0:
                    found = pno
                    break
            if found is not None:
                break
        if found is not None:
            pages[slug] = found + 1
            cursor = found
    doc.close()
    return pages


def post_process(pdf_path: Path, headings, pages: dict[str, int]) -> None:
    doc = fitz.open(pdf_path)
    n = doc.page_count
    for pno in range(n):
        if pno == 0:
            continue
        page = doc[pno]
        w, h = page.rect.width, page.rect.height
        y = h - 28
        page.insert_text((45, y), FOOTER_LEFT, fontsize=7.5, fontname="helv", color=(0.42, 0.46, 0.52))
        label = f"Page {pno + 1} of {n}"
        tw = fitz.get_text_length(label, fontname="helv", fontsize=7.5)
        page.insert_text((w - 45 - tw, y), label, fontsize=7.5, fontname="helv", color=(0.42, 0.46, 0.52))
    toc = [[1, "Cover", 1], [1, "Contents", 2]]
    for level, text, slug in headings:
        if slug in pages:
            toc.append([level - 1, text, pages[slug]])
    doc.set_toc(toc)
    doc.set_metadata({
        "title": DOC_TITLE, "subject": DOC_SUB, "author": "Team Ctrl+Alt+Hiru",
        "keywords": "AI Builder Cup 2026, BFSI, Google Cloud, Gemini, wealth management",
    })
    tmp = pdf_path.with_suffix(".tmp.pdf")
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)


def main() -> None:
    md_text = strip_front_matter(MD_PATH.read_text(encoding="utf-8"))
    headings = extract_headings(md_text)
    body = md_to_body_html(md_text)
    work = Path(tempfile.mkdtemp(prefix="atrium-pdf-"))
    html_path = work / "blueprint.html"
    pass1 = work / "pass1.pdf"

    # Pass 1: no page numbers in the TOC; find where each heading landed.
    html_path.write_text(wrap_html(body, build_toc_html(headings, None)), encoding="utf-8")
    render_pdf(html_path, pass1)
    pages = locate_headings(pass1, headings)

    # Pass 2: TOC with page numbers (same line count, so pagination is stable).
    html_path.write_text(wrap_html(body, build_toc_html(headings, pages)), encoding="utf-8")
    render_pdf(html_path, PDF_PATH)
    pages2 = locate_headings(PDF_PATH, headings)
    if pages2 != pages:
        # Pagination moved; one more pass with the corrected numbers.
        html_path.write_text(wrap_html(body, build_toc_html(headings, pages2)), encoding="utf-8")
        render_pdf(html_path, PDF_PATH)
        pages = locate_headings(PDF_PATH, headings)
    else:
        pages = pages2
    post_process(PDF_PATH, headings, pages)

    missing = [t for _, t, s in headings if s not in pages]
    doc = fitz.open(PDF_PATH)
    print(f"OK {PDF_PATH} pages={doc.page_count} headings={len(headings)} located={len(pages)}")
    if missing:
        print("Headings not located:", missing)
    doc.close()
    shutil.copy(html_path, work / "blueprint.final.html")
    print("work dir:", work)


if __name__ == "__main__":
    sys.exit(main())

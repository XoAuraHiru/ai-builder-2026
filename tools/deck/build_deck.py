"""Build the Atrium pitch deck on the AI Builder Cup submission template.

The template's slides, order, header and footer art and title text boxes are kept; the instruction slide is
removed and every other slide is filled. Every figure on the slides is a measured number from the live
deployment or an estimate that says so.

Run from the repo root:

    uv run --no-project --with python-pptx python tools/deck/build_deck.py

Writes docs/pitch/Atrium-Pitch-Deck.pptx (fonts embedded) and docs/pitch/Atrium-Pitch-Deck.pdf through
PowerPoint on Windows (COM). Options:
    --png DIR      also export every slide as a 1920x1080 PNG into DIR
    --no-office    skip PowerPoint; write the python-pptx file only (no PDF, fonts not embedded)
    --template F   use another copy of the submission template

Inputs: tools/deck/submission-template.pptx (a copy of the official template), the screenshots in
.superpowers/snapshots and the draw.io exports in docs/diagrams.
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree
from PIL import Image, ImageChops, ImageFont
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION, XL_TICK_MARK
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

# --- links: fill the two video links, then rebuild -------------------------------------------------------
LINKS = {
    "github": "https://github.com/XoAuraHiru/ai-builder-2026",
    "video_short": "https://drive.google.com/file/d/1TMCX9mcsYh2S9Ca4jIuyHXmKU__NnDYG/view?usp=sharing",  # the demo video, 3:54
    "video_long": "https://drive.google.com/file/d/1oD3D53ct0aEXTA_hwY-hcXpCRqnd_Fpz/view?usp=sharing",  # the extended walkthrough, 9:02
    "product": "https://atrium-cup-2026.web.app",
    "product_alt": "https://atrium-web-tvflgkcdoa-uc.a.run.app",
}

ROOT = Path(__file__).resolve().parents[2]
DECK_DIR = Path(__file__).resolve().parent
TEMPLATE_COPY = DECK_DIR / "submission-template.pptx"
TEMPLATE_DOWNLOAD = Path.home() / "Downloads" / "Submission Template _ AI Builder Cup.pptx"
SNAP = ROOT / ".superpowers" / "snapshots"
DIAG = ROOT / "docs" / "diagrams"
OUT_DIR = ROOT / "docs" / "pitch"
OUT_PPTX = OUT_DIR / "Atrium-Pitch-Deck.pptx"
OUT_PDF = OUT_DIR / "Atrium-Pitch-Deck.pdf"

# --- the Atrium design system -----------------------------------------------------------------------------
INK, MUTED, HAIR, WASH, WHITE = "1C1B17", "6F6C62", "EBEAE4", "FAFAF7", "FFFFFF"
LINE = HAIR  # card and screenshot edges
GREEN, GREEN_TINT = "3F8160", "E0EDE4"  # action, money, "a person decides"
VIOLET, VIOLET_DK, VIOLET_TINT = "7C74DB", "4B44A6", "F2F1FC"  # only for Gemini and AI
CORAL, CORAL_DK, CORAL_TINT = "E8705F", "B23F2E", "FDEDEA"  # only for risk and fraud
AMBER, AMBER_DK, AMBER_TINT = "E2B23E", "8A6A12", "FCF3D9"  # only for Firebase

REG, MED, SEMI = "Google Sans Flex", "Google Sans Flex Medium", "Google Sans Flex SemiBold"

# content area: the title text sits at x 0.39 in; the black header bar is above, the footer line below
L, R = 0.39, 9.61
W = R - L
TOP, BOT = 1.32, 5.40


def rgb(hexstr: str) -> RGBColor:
    return RGBColor.from_string(hexstr)


def In(v: float) -> Emu:
    return Emu(int(round(v * 914400)))


# --- text --------------------------------------------------------------------------------------------------
class T:
    """A run of text; unset style falls back to its paragraph's."""

    def __init__(self, text, size=None, font=None, color=None, bold=False, link=None):
        self.text, self.size, self.font, self.color, self.bold, self.link = text, size, font, color, bold, link


class P:
    """A paragraph: runs plus paragraph options. Strings become runs in the paragraph style."""

    def __init__(self, *runs, size=11, font=REG, color=INK, align="l", before=0, after=0, line=1.0,
                 bullet=None, bullet_color=None, indent=0.16):
        self.runs = [r if isinstance(r, T) else T(r) for r in runs]
        self.size, self.font, self.color = size, font, color
        self.align, self.before, self.after, self.line = align, before, after, line
        self.bullet, self.bullet_color, self.indent = bullet, bullet_color, indent


ALIGN = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}
ANCHOR = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}


def set_typeface(run, face: str) -> None:
    run.font.name = face
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs", "a:sym"):
        for el in rPr.findall(qn(tag)):
            rPr.remove(el)
    prev = rPr.find(qn("a:latin"))
    for tag in ("a:ea", "a:cs", "a:sym"):
        el = rPr.makeelement(qn(tag), {"typeface": face})
        prev.addnext(el)
        prev = el


def style_run(run, size, font, color, bold=False, link=None) -> None:
    run.font.size = Pt(size)
    run.font.bold = bool(bold)
    run.font.italic = False
    run.font.color.rgb = rgb(color)
    set_typeface(run, font)
    if link:
        run.hyperlink.address = link  # coloured by the theme's link colour, set to Atrium green in build()


def set_bullet(p, char, color, indent):
    pPr = p._p.get_or_add_pPr()
    for tag in ("a:buClr", "a:buSzPct", "a:buFont", "a:buChar", "a:buNone", "a:buAutoNum"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    if char is None:
        etree.SubElement(pPr, qn("a:buNone"))
        return
    pPr.set("marL", str(int(In(indent))))
    pPr.set("indent", str(-int(In(indent))))
    clr = etree.SubElement(pPr, qn("a:buClr"))
    etree.SubElement(clr, qn("a:srgbClr"), val=color)
    etree.SubElement(pPr, qn("a:buSzPct"), val="100000")
    etree.SubElement(pPr, qn("a:buFont"), typeface=REG)
    etree.SubElement(pPr, qn("a:buChar"), char=char)


def fill_paragraphs(tf, paras) -> None:
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ALIGN[para.align]
        p.line_spacing = para.line
        p.space_before = Pt(para.before)
        p.space_after = Pt(para.after)
        set_bullet(p, para.bullet, para.bullet_color or MUTED, para.indent)
        for t in para.runs:
            parts = t.text.split("\n")
            for k, part in enumerate(parts):
                if k:
                    p.add_line_break()
                if not part:
                    continue
                r = p.add_run()
                r.text = part
                style_run(r, t.size or para.size, t.font or para.font, t.color or para.color, t.bold, t.link)
        end = p._p.find(qn("a:endParaRPr"))
        if end is None:
            end = etree.SubElement(p._p, qn("a:endParaRPr"))
        end.set("sz", str(int(para.size * 100)))


def text(slide, x, y, w, h, paras, anchor="t", margins=(0, 0, 0, 0), check=True, name=None):
    if isinstance(paras, P):
        paras = [paras]
    tb = slide.shapes.add_textbox(In(x), In(y), In(w), In(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left, tf.margin_top, tf.margin_right, tf.margin_bottom = (In(m) for m in margins)
    tf.vertical_anchor = ANCHOR[anchor]
    fill_paragraphs(tf, paras)
    if name:
        tb.name = name
    if check:
        need = estimate_height(paras, w - margins[0] - margins[2]) + margins[1] + margins[3]
        if need > h + 0.02:
            first = paras[0].runs[0].text[:40] if paras and paras[0].runs else ""
            WARNINGS.append(f"slide {CURRENT[0]}: text may overflow ({need:.2f} in > {h:.2f} in): {first!r}")
    return tb


# --- a rough text-fit check (greedy wrap with the real font metrics) ---------------------------------------
WARNINGS: list[str] = []
CURRENT = [0]
_FONT_FILES = {REG: "GoogleSansFlex-400.ttf", MED: "GoogleSansFlex-500.ttf", SEMI: "GoogleSansFlex-600.ttf"}
_FONT_CACHE: dict = {}


def _pil_font(face, bold=False):
    key = (face, bold)
    if key not in _FONT_CACHE:
        name = "GoogleSansFlex-700.ttf" if (bold and face == REG) else _FONT_FILES.get(face, _FONT_FILES[REG])
        path = None
        for d in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts", Path(r"C:\Windows\Fonts")):
            if (d / name).exists():
                path = d / name
                break
        _FONT_CACHE[key] = ImageFont.truetype(str(path), 1000) if path else None
    return _FONT_CACHE[key]


def estimate_height(paras, width_in) -> float:
    total = 0.0
    width_pt = width_in * 72
    for para in paras:
        indent_pt = para.indent * 72 if para.bullet else 0
        avail = width_pt - indent_pt
        lines, cur, cur_size = [], 0.0, 0.0
        words = []
        for t in para.runs:
            f = _pil_font(t.font or para.font, t.bold)
            size = t.size or para.size
            for k, chunk in enumerate(t.text.split("\n")):
                if k:
                    words.append(("\n", 0, size))
                for wd in chunk.split(" "):
                    if f is None:
                        wpt = len(wd) * size * 0.5
                        spt = size * 0.25
                    else:
                        wpt = f.getlength(wd) / 1000 * size
                        spt = f.getlength(" ") / 1000 * size
                    words.append((wd, wpt, size, spt))
        for item in words:
            if item[0] == "\n":
                lines.append(cur_size or para.size)
                cur, cur_size = 0.0, 0.0
                continue
            wd, wpt, size, spt = item
            add = wpt if cur == 0 else spt + wpt
            if cur and cur + add > avail:
                lines.append(cur_size)
                cur, cur_size = wpt, size
            else:
                cur += add
                cur_size = max(cur_size, size)
        lines.append(cur_size or para.size)
        total += sum(s * 1.2 * para.line for s in lines) + para.before + para.after
    return total / 72


# --- shapes ------------------------------------------------------------------------------------------------
def _plain(shape):
    st = shape._element.find(qn("p:style"))
    if st is not None:
        shape._element.remove(st)
    return shape


def box(slide, x, y, w, h, fill=WHITE, line=LINE, lw=1.0, r=0.1, shape=None):
    kind = shape or (MSO_SHAPE.ROUNDED_RECTANGLE if r else MSO_SHAPE.RECTANGLE)
    s = _plain(slide.shapes.add_shape(kind, In(x), In(y), In(w), In(h)))
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(0.5, r / min(w, h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def label_in(shape, paras, anchor="m", margins=(0.08, 0.02, 0.08, 0.02)):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left, tf.margin_top, tf.margin_right, tf.margin_bottom = (In(m) for m in margins)
    tf.vertical_anchor = ANCHOR[anchor]
    fill_paragraphs(tf, [paras] if isinstance(paras, P) else paras)
    return shape


def pill(slide, x, y, w, h, words, fill, color, size=9, font=MED, line=None, align="c"):
    s = box(slide, x, y, w, h, fill=fill, line=line, r=h / 2)
    return label_in(s, P(words, size=size, font=font, color=color, align=align), margins=(0.06, 0, 0.06, 0))


def circle(slide, x, y, d, fill, words="", color=WHITE, size=9, font=SEMI, line=None):
    s = box(slide, x, y, d, d, fill=fill, line=line, shape=MSO_SHAPE.OVAL)
    if words:
        label_in(s, P(words, size=size, font=font, color=color, align="c"), margins=(0, 0, 0, 0))
    return s


def rule(slide, x1, y1, x2, y2, color=HAIR, lw=0.75, arrow=False, dash=False):
    c = _plain(slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, In(x1), In(y1), In(x2), In(y2)))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(lw)
    ln = c.line._get_or_add_ln()
    if dash:
        etree.SubElement(ln, qn("a:prstDash"), val="dash")
    if arrow:
        etree.SubElement(ln, qn("a:tailEnd"), type="triangle", w="med", len="med")
    return c


def sparkle(slide, x, y, d, color=VIOLET):
    """The Gemini mark: a four-point star."""
    s = box(slide, x, y, d, d, fill=color, line=None, shape=MSO_SHAPE.STAR_4_POINT)
    s.adjustments[0] = 0.16
    return s


def check_mark(slide, x, y, d, color=GREEN, lw=1.6):
    # freeform points are whole local units, so work in EMU (scale 1) rather than inches
    fb = slide.shapes.build_freeform(In(x + d * 0.1), In(y + d * 0.55), scale=1.0)
    fb.add_line_segments([(In(x + d * 0.4), In(y + d * 0.82)), (In(x + d * 0.9), In(y + d * 0.22))], close=False)
    s = _plain(fb.convert_to_shape())
    s.fill.background()
    s.line.color.rgb = rgb(color)
    s.line.width = Pt(lw)
    return s


def graph_glyph(slide, x, y, d, color=CORAL_DK):
    """Three linked dots: the identity graph."""
    pts = [(x + d * 0.18, y + d * 0.7), (x + d * 0.5, y + d * 0.22), (x + d * 0.82, y + d * 0.7)]
    rule(slide, *pts[0], *pts[1], color=color, lw=1.1)
    rule(slide, *pts[1], *pts[2], color=color, lw=1.1)
    rule(slide, *pts[0], *pts[2], color=color, lw=1.1)
    r = d * 0.13
    for px, py in pts:
        circle(slide, px - r, py - r, 2 * r, fill=color)


def icon_disc(slide, x, y, d, kind):
    tint = {"ai": VIOLET_TINT, "person": GREEN_TINT, "fraud": CORAL_TINT, "firebase": AMBER_TINT}[kind]
    circle(slide, x, y, d, fill=tint)
    g = d * 0.56
    gx, gy = x + (d - g) / 2, y + (d - g) / 2
    if kind == "ai":
        sparkle(slide, gx, gy, g)
    elif kind == "person":
        check_mark(slide, gx, gy, g)
    elif kind == "fraud":
        graph_glyph(slide, gx, gy, g)
    else:
        circle(slide, x + d * 0.34, y + d * 0.34, d * 0.32, fill=AMBER)


def person(slide, x, y, initials, d=0.3, size=8):
    return circle(slide, x, y, d, fill=GREEN_TINT, words=initials, color=GREEN, size=size)


# --- pictures ----------------------------------------------------------------------------------------------
def _round_picture(pic, w, h, r):
    pic.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
    geom = pic._element.spPr.find(qn("a:prstGeom"))
    av = geom.find(qn("a:avLst"))
    if av is None:
        av = etree.SubElement(geom, qn("a:avLst"))
    for g in list(av):
        av.remove(g)
    etree.SubElement(av, qn("a:gd"), name="adj", fmla=f"val {int(min(50000, r / min(w, h) * 100000))}")


def shot(slide, fname, x, y, w, h, crop, r=0.06, border=LINE):
    """A screenshot cropped to `crop` = (x0, y0, x1) in a 2000-px-wide view; the height follows the box."""
    path = SNAP / fname
    iw, ih = Image.open(path).size
    k = iw / 2000.0
    x0, y0, x1 = crop[0] * k, crop[1] * k, crop[2] * k
    ph = (x1 - x0) * h / w
    y1 = y0 + ph
    if y1 > ih:
        y0, y1 = max(0, ih - ph), ih
    pic = slide.shapes.add_picture(str(path), In(x), In(y), In(w), In(h))
    pic.crop_left, pic.crop_right = x0 / iw, 1 - x1 / iw
    pic.crop_top, pic.crop_bottom = y0 / ih, 1 - y1 / ih
    _round_picture(pic, w, h, r)
    pic.line.color.rgb = rgb(border)
    pic.line.width = Pt(0.75)
    return pic


def diagram(slide, fname, x, y, max_w, max_h, align="c"):
    """A draw.io export with its white margin trimmed, as large as fits the box. Returns (x, y, w, h)."""
    path = DIAG / fname
    if not path.exists():
        box(slide, x, y, max_w, max_h, fill=WASH, line=LINE, r=0.1)
        text(slide, x, y + max_h / 2 - 0.2, max_w, 0.4,
             P(f"Diagram to come: docs/diagrams/{fname}", size=12, color=MUTED, align="c"))
        WARNINGS.append(f"slide {CURRENT[0]}: placeholder for missing {fname}")
        return x, y, max_w, max_h
    im = Image.open(path).convert("RGB")
    iw, ih = im.size
    diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L")
    bx0, by0, bx1, by1 = diff.point(lambda v: 255 if v > 8 else 0).getbbox()
    pad = 12
    bx0, by0, bx1, by1 = max(0, bx0 - pad), max(0, by0 - pad), min(iw, bx1 + pad), min(ih, by1 + pad)
    aspect = (bx1 - bx0) / (by1 - by0)
    w = min(max_w, max_h * aspect)
    h = w / aspect
    px = x + (max_w - w) / 2 if align == "c" else x
    pic = slide.shapes.add_picture(str(path), In(px), In(y), In(w), In(h))
    pic.crop_left, pic.crop_right = bx0 / iw, 1 - bx1 / iw
    pic.crop_top, pic.crop_bottom = by0 / ih, 1 - by1 / ih
    return px, y, w, h


# --- template plumbing -------------------------------------------------------------------------------------
def delete_slide(prs, index):
    lst = prs.slides._sldIdLst
    sld = lst[index]
    prs.part.drop_rel(sld.rId)
    lst.remove(sld)


def text_shape(slide, startswith):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip().startswith(startswith):
            return sh
    raise LookupError(f"no text box starting with {startswith!r}")


def drop_paragraphs_after(tf, keep):
    for p in tf.paragraphs[keep:]:
        p._p.getparent().remove(p._p)


# =========================================================================================================
# slides
# =========================================================================================================
def s_title(slide):
    tb = text_shape(slide, "Team Details")
    tf = tb.text_frame
    ps = tf.paragraphs
    # p0 "Team Details" stays; p1 is the gap; p2..p4 are the template's a. b. c. items
    ps[1]._p.find(qn("a:endParaRPr")).set("sz", "900")
    values = [
        [T("Ctrl+Alt+Hiru", font=SEMI)],
        [T("Hirun Chamara", font=SEMI)],
        [T("BFSI · Intelligent Risk, Fraud & Financial Experiences: ", font=SEMI),
         T("wealth firms run each client on separate systems, fraud slips through the gaps, "
           "and bolted-on AI is a black box.")],
    ]
    size = 15
    for p, runs in zip(ps[2:5], values):
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.color.rgb = rgb(INK)
        p._p.find(qn("a:pPr")).find(qn("a:buSzPts")).set("val", str(size * 100))
        for t in runs:
            r = p.add_run()
            r.text = t.text
            style_run(r, size, t.font or REG, INK)
        end = p._p.find(qn("a:endParaRPr"))
        p._p.remove(end)
        p._p.append(end)
        end.set("sz", str(size * 100))
    drop_paragraphs_after(tf, 5)

    # the product, beside "Team Details"
    x = 6.42
    tile = box(slide, x, 3.30, 0.46, 0.46, fill=GREEN_TINT, line=None, r=0.1)
    label_in(tile, P("A", size=19, font=SEMI, color=GREEN, align="c"), margins=(0, 0, 0, 0.02))
    text(slide, x + 0.58, 3.24, 2.7, 0.34, P("Atrium", size=19, font=SEMI))
    text(slide, x + 0.58, 3.58, 2.7, 0.22, P("People decide. The AI shows its working.", size=10, color=MUTED))


def s_brief(slide):
    # left: the idea in one line, the lifecycle, and the two rules
    text(slide, L, 1.30, 5.3, 0.64, P(T("Atrium: ", color=GREEN), "one AI-native platform for the whole client life "
                                      "of a wealth firm.", size=18, font=SEMI, line=0.98))
    stages = [("01", "Acquire"), ("02", "Invest"), ("03", "Trade"), ("04", "Operate")]
    cw, gap, cy, ch = 1.1, 0.27, 2.04, 0.32
    for i, (n, name) in enumerate(stages):
        cx = L + i * (cw + gap)
        s = box(slide, cx, cy, cw, ch, fill=WHITE, line=LINE, r=ch / 2)
        label_in(s, P(T(n + "  ", size=8.5, font=MED, color=MUTED), T(name, font=MED), size=10.5, align="c"),
                 margins=(0.04, 0, 0.04, 0))
        if i:
            rule(slide, cx - gap + 0.05, cy + ch / 2, cx - 0.05, cy + ch / 2, color=MUTED, lw=1.0, arrow=True)
    band_w = 4 * cw + 3 * gap
    band = box(slide, L, 2.44, band_w, 0.28, fill=WASH, line=LINE, r=0.14)
    label_in(band, P(T("Govern  ", font=MED, color=INK), "compliance across all four", size=10, color=MUTED,
                     align="c"))
    icon_disc(slide, L, 2.84, 0.26, "ai")
    text(slide, L + 0.37, 2.84, 4.8, 0.26, P(T("Gemini", font=SEMI, color=VIOLET_DK), " works at every stage",
                                            size=12.5), anchor="m")
    icon_disc(slide, L, 3.16, 0.26, "person")
    text(slide, L + 0.37, 3.16, 4.8, 0.26, P(T("A person", font=SEMI, color=GREEN), " makes every decision",
                                            size=12.5), anchor="m")

    # right: the real front door
    shot(slide, "public-front-door.png", 5.95, 1.32, 3.66, 2.1, (150, 0, 1850))

    # bottom: three pillars
    pillars = [
        ("fraud", "One platform, one identity graph",
         "Leads, portfolios, orders and the ledger share one data model, so a device seen on a fraudulent lead "
         "is recognised when it signs in to a client's account."),
        ("ai", "AI that shows its working",
         "Every dollar and percentage Gemini writes is checked against Atrium's engines; citations are "
         "restricted to real evidence; a tripwire stops steered text from closing an alert."),
        ("person", "Governed like a regulated model",
         "A built-in Model Risk Office: golden tests gate every deploy, a red team attacks the live models, "
         "circuit breakers pause what drifts, and every AI decision is logged with its model and cost."),
    ]
    gap = 0.15
    pw = (W - 2 * gap) / 3
    py, ph = 3.6, BOT - 3.6
    for i, (kind, title, body) in enumerate(pillars):
        px = L + i * (pw + gap)
        box(slide, px, py, pw, ph, fill=WHITE, line=LINE, r=0.12)
        icon_disc(slide, px + 0.17, py + 0.17, 0.36, kind)
        text(slide, px + 0.64, py + 0.17, pw - 0.8, 0.36, P(title, size=12, font=SEMI, line=0.95), anchor="m")
        text(slide, px + 0.17, py + 0.66, pw - 0.3, ph - 0.7, P(body, size=11, line=0.98))


def s_opportunities(slide):
    tb = text_shape(slide, "Opportunities")
    tf = tb.text_frame
    p0 = tf.paragraphs[0]
    for br in p0._p.findall(qn("a:br")):
        p0._p.remove(br)
    drop_paragraphs_after(tf, 1)
    tb.height = In(0.6145)

    gap = 0.15
    widths = [2.92, 3.38, 2.62]
    xs = [L, L + widths[0] + gap, L + widths[0] + widths[1] + 2 * gap]
    y, h = TOP, BOT - TOP
    heads = ["How different is it from any of the other existing ideas?",
             "How will it be able to solve the problem?",
             "USP of the proposed solution"]
    for i in range(3):
        fill = GREEN_TINT if i == 2 else WHITE
        box(slide, xs[i], y, widths[i], h, fill=fill, line=None if i == 2 else LINE, r=0.12)
        circle(slide, xs[i] + 0.18, y + 0.2, 0.26, fill=INK if i < 2 else GREEN, words=str(i + 1), size=9)
        text(slide, xs[i] + 0.54, y + 0.15, widths[i] - 0.72, 0.42, P(heads[i], size=12, font=SEMI, line=0.95),
             anchor="m")
        rule(slide, xs[i] + 0.18, y + 0.72, xs[i] + widths[i] - 0.18, y + 0.72, color=HAIR if i < 2 else "C9DDCF")

    # 1: how it differs
    x, w = xs[0] + 0.18, widths[0] - 0.36
    text(slide, x, y + 0.86, w, 1.25, P(
        "Today's wealth tech adds AI to one system at a time. Atrium is AI-native across the whole lifecycle, "
        "with one identity graph and one decision log, so fraud can't hide in the hand-offs.", size=11))
    text(slide, x, y + 2.12, w, 0.22, P("For example", size=9.5, font=MED, color=MUTED))
    examples = [("fraud", "A fraud ring radar across the whole lifecycle"),
                ("fraud", "Account-takeover detection in the Pre-trade Guardian"),
                ("ai", "Call intelligence grounded in the transcript, with timestamps")]
    for k, (kind, words) in enumerate(examples):
        ey = y + 2.4 + k * 0.54
        icon_disc(slide, x, ey + 0.03, 0.26, kind)
        text(slide, x + 0.36, ey, w - 0.36, 0.44, P(words, size=10.5, line=0.98), anchor="m")

    # 2: how it solves the problem
    x, w = xs[1] + 0.18, widths[1] - 0.36
    points = [
        ("Acquire", "Leads scored twice (BigQuery ML fit + Trust Score) and identity-proofed with Document AI "
                    "before an advisor calls."),
        ("Trade", "Every order checked before it reaches the market: suitability, concentration, liquidity, "
                  "account takeover."),
        ("Operate", "The back office automated under four-eyes control: Document AI + an ADK agent for "
                    "reconciliation, approvals with one-time codes."),
        ("Govern", "Seven AML scenarios and a BigQuery ML anomaly model, with a Gemini Pro case review citing "
                   "only evidence."),
    ]
    text(slide, x, y + 0.86, w, h - 0.98, [
        P(T(stage + "  ", font=SEMI, color=GREEN), body, size=11, after=7) for stage, body in points])

    # 3: the USP
    x, w = xs[2] + 0.18, widths[2] - 0.36
    text(slide, x, y + 0.84, w, 0.86, [P("People decide.", size=17, font=SEMI, color=GREEN, line=0.92),
                                       P("The AI shows its working.", size=17, font=SEMI, color=INK, line=0.92)])
    usp = ["Every figure checked against deterministic engines",
           "A Model Risk Office with live red-team and fair-lending tests",
           "Real time across every person through Firestore"]
    text(slide, x, y + 1.8, w, 1.52, [P(u, size=11, bullet="•", bullet_color=GREEN, after=5, indent=0.15)
                                      for u in usp])
    rule(slide, x, y + 3.3, x + w, y + 3.3, color="C9DDCF")
    text(slide, x, y + 3.38, w, 0.6, P(T("Measured live: ", font=MED), "37/37 model-check suites, 29/29 "
                                       "red-team attacks resisted, 18/18 fair-lending pairs", size=9.5, color=INK))


AI_TERMS = ["Google Search grounding", "Vertex AI Search", "Gemini audio", "Gemini Pro", "BigQuery ML",
            "Document AI", "ADK agent", "Gemini", "ADK"]


def tech_runs(words, color=MUTED):
    """Split text into runs, with Google AI product names in Gemini violet."""
    runs, i = [], 0
    while i < len(words):
        hit = None
        for term in AI_TERMS:
            j = words.find(term, i)
            if j != -1 and (hit is None or j < hit[0]):
                hit = (j, term)
        if hit is None:
            runs.append(T(words[i:], color=color))
            break
        j, term = hit
        if j > i:
            runs.append(T(words[i:j], color=color))
        runs.append(T(term, color=VIOLET_DK, font=MED))
        i = j + len(term)
    return runs


def s_features(slide):
    cols = [
        ("01", "Acquire", "Daniel, advisor", [
            ("Lead Score + Trust Score", "BigQuery ML fit; fraud signals score trust"),
            ("Identity proofing", "Document AI"),
            ("Call intelligence", "Gemini audio, timestamped conduct flags"),
            ("Personalised proposals", "Gemini Pro, cited and checked"),
            ("Advisor agents", "ADK"),
        ]),
        ("02", "Invest", "Priya, Lucas", [
            ("Risk profile", "chosen with Gemini"),
            ("Risk drift and analytics", None),
            ("What-if Studio", "10,000 simulated futures; Gemini explains"),
            ("Portfolio X-ray", "look-through to every company"),
            ("Scenario Studio", "Gemini + Google Search grounding"),
            ("Fund fit", "Vertex AI Search, cited"),
            ("Investor Copilot", "an ADK agent"),
        ]),
        ("03", "Trade", "Priya, Tom, Daniel", [
            ("Live US stock and ETF prices", "with a paper broker"),
            ("Pre-trade Guardian", "proceed, warn, hold or block"),
            ("Account-takeover detection", "device trust"),
            ("Held-order queue", "Gemini Pro review note"),
            ("Live inbox", "Cloud Firestore, real time"),
        ]),
        ("04", "Operate", "Mei, Sam", [
            ("Day-end job", "Cloud Run job on Cloud Scheduler; Gemini morning brief"),
            ("Bank statements", "read by Document AI"),
            ("Reconciliation", "rules + an ADK agent"),
            ("Four-eyes approvals", "one-time codes"),
            ("Fund pricing guard", None),
        ]),
        ("", "Govern", "Omar, across all four", [
            ("AML monitoring", "7 scenarios + a BigQuery ML anomaly model"),
            ("Case review", "Gemini Pro; evidence-only citations and a tripwire"),
            ("Fraud ring radar", "one identity graph"),
            ("Model Risk Office", "18 models: golden tests, red team, fair lending, circuit breakers"),
            ("AI decision log", "model, cost, who acted"),
        ]),
    ]
    gap = 0.1
    cw = (W - 4 * gap) / 5
    top, strip_h = TOP, 0.3
    ch = BOT - strip_h - 0.12 - top
    for i, (num, stage, people, items) in enumerate(cols):
        cx = L + i * (cw + gap)
        fill = WASH if stage == "Govern" else WHITE
        box(slide, cx, top, cw, ch, fill=fill, line=LINE, r=0.1)
        text(slide, cx + 0.11, top + 0.1, cw - 0.2, 0.26,
             P(T(num + "  ", size=9, font=MED, color=MUTED) if num else T(""), T(stage), size=12.5, font=SEMI),
             anchor="m")
        text(slide, cx + 0.11, top + 0.37, cw - 0.2, 0.2, P(people, size=9, color=GREEN, font=MED), anchor="m")
        rule(slide, cx + 0.11, top + 0.64, cx + cw - 0.11, top + 0.64, color=HAIR)
        paras = []
        for name, detail in items:
            paras.append(P(name, size=10, font=SEMI, before=4.5 if paras else 0, line=0.98))
            if detail:
                paras.append(P(*tech_runs(detail), size=9, line=0.98))
        text(slide, cx + 0.11, top + 0.72, cw - 0.19, ch - 0.78, paras)
    sy = BOT - strip_h
    strip = box(slide, L, sy, W, strip_h, fill=WASH, line=LINE, r=strip_h / 2)
    label_in(strip, P(T("Before sign-in  ", font=SEMI, color=GREEN), "a public return analyzer: 10,000 futures "
                      "drawn from real markets since 2007", size=10, color=INK, align="l"),
             margins=(0.2, 0, 0.2, 0))
    text(slide, R - 3.2, sy, 3.0, strip_h, P(T("Violet", font=MED, color=VIOLET_DK), ": Google AI at work", size=9,
                                             color=MUTED, align="r"), anchor="m")


def _pil_text_width(s, face, size):
    f = _pil_font(face)
    return (f.getlength(s) / 1000 * size / 72) if f else len(s) * size * 0.5 / 72


def s_flow(slide):
    x, y, w, h = diagram(slide, "atrium-lifecycle-flow.png", L, TOP - 0.02, W, 3.8)
    text(slide, x + 0.05, y + h + 0.08, w, 0.24, P(
        T("One client's life, end to end. ", font=MED, color=INK),
        "Gemini works at every stage; a person makes every decision.", size=10, color=MUTED))


def s_mocks(slide):
    text(slide, L, 1.28, W, 0.3, P(T("From lead to ledger  ", size=13, font=SEMI),
                                   T("six real screens from the live prototype, in the order a client meets them",
                                     size=10, color=MUTED)), anchor="m")
    cells = [
        ("daniel-leads-triage.png", (200, 355, 1350),
         "Acquire: leads scored for fit and trust; four from one device are flagged first"),
        ("daniel-ruth-call-transcript.png", (200, 262, 1240),
         "Call intelligence: Gemini hears the call; each conduct flag sits at its second"),
        ("priya-what-if-explained.png", (615, 120, 1820),
         "Invest: 10,000 futures; Gemini explains them, every figure checked"),
        ("daniel-held-review-note.png", (1080, 115, 1965),
         "Trade: the Pre-trade Guardian holds an order; Gemini Pro drafts the review note"),
        ("mei-reconciliation-proposals.png", (172, 95, 1965),
         "Operate: the reconciliation agent proposes; a person accepts or rejects"),
        ("omar-alert-structuring-case-review.png", (180, 40, 1210),
         "Govern: Gemini Pro reviews the AML case, citing only the evidence"),
    ]
    gx, gy = 0.2, 0.12
    cw = (W - 2 * gx) / 3
    top = 1.68
    rh = (BOT - top - gy) / 2
    ih = rh - 0.4
    for i, (fname, crop, cap) in enumerate(cells):
        cx = L + (i % 3) * (cw + gx)
        cy = top + (i // 3) * (rh + gy)
        shot(slide, fname, cx, cy, cw, ih, crop)
        circle(slide, cx, cy + ih + 0.09, 0.24, fill=INK, words=str(i + 1), size=9)
        text(slide, cx + 0.32, cy + ih + 0.05, cw - 0.32, 0.34, P(cap, size=9.5, line=0.95), anchor="m")


def s_architecture(slide):
    x, y, w, h = diagram(slide, "atrium-architecture.png", L, TOP - 0.02, W, 3.8)
    text(slide, x + 0.05, y + h + 0.08, w, 0.24, P(
        "Everything runs in Google Cloud project ", T("atrium-cup-2026", font=MED, color=INK), ", ",
        T("us-central1", font=MED, color=INK), ". Numbers trace a request; letters trace the live inbox.",
        size=10, color=MUTED))


def s_tech(slide):
    # the brief's stack, highlighted
    by, bh = TOP, 1.12
    box(slide, L, by, W, bh, fill=WASH, line=LINE, r=0.12)
    text(slide, L + 0.2, by + 0.12, 1.7, bh - 0.24, [P("The brief's stack,", size=12.5, font=SEMI, line=0.95),
                                                     P("all in production", size=12.5, font=SEMI, line=0.95,
                                                       color=GREEN)], anchor="m")
    tiles = [
        ("firebase", "Firebase", "Hosting front door + Auth custom tokens", AMBER_TINT),
        ("firebase", "Cloud Firestore", "Live inbox: real-time onSnapshot with security rules", AMBER_TINT),
        (None, "Cloud Run", "Web app, API, day-end and evals jobs", WHITE),
        ("ai", "Gemini", "3.1 Pro and 3.8 Flash on Vertex AI", VIOLET_TINT),
    ]
    tx0 = L + 2.05
    tgap = 0.1
    tw = (R - 0.12 - tx0 - 3 * tgap) / 4
    for i, (kind, name, desc, fill) in enumerate(tiles):
        tx = tx0 + i * (tw + tgap)
        box(slide, tx, by + 0.12, tw, bh - 0.24, fill=fill, line=None if fill != WHITE else LINE, r=0.09)
        if kind == "ai":
            sparkle(slide, tx + 0.13, by + 0.25, 0.17)
        elif kind == "firebase":
            circle(slide, tx + 0.15, by + 0.28, 0.13, fill=AMBER)
        else:
            circle(slide, tx + 0.15, by + 0.28, 0.13, fill=MUTED)
        text(slide, tx + 0.38, by + 0.2, tw - 0.48, 0.24, P(name, size=11, font=SEMI), anchor="m")
        text(slide, tx + 0.13, by + 0.47, tw - 0.24, 0.52, P(desc, size=9.5, color=INK, line=0.98))

    # the rest of Google Cloud, and the app
    ty = by + bh + 0.14
    th = BOT - ty
    gap = 0.15
    cw = (W - gap) / 2
    ai_rows = [
        ("Gemini on Vertex AI", "explanations, proposals, case reviews, call audio, Google Search grounding, "
                                "TTS for demo calls"),
        ("Agent Development Kit", "Investor Copilot, reconciliation agent, advisor concierge with lead-intelligence "
                                  "and trust-and-fraud sub-agents"),
        ("Document AI", "identity proofing, bank statement parser"),
        ("Vertex AI Search", "fund documents"),
        ("BigQuery + BigQuery ML", "Lead Score model, AML k-means anomaly model, events"),
    ]
    data_rows = [
        ("Cloud SQL for PostgreSQL", "the ledger and every record"),
        ("Pub/Sub", "event stream to BigQuery"),
        ("Platform", "Cloud Storage, Cloud Scheduler, Secret Manager, Cloud Build + Artifact Registry"),
        ("Web app", "Next.js 15, React, Tailwind CSS v4, Motion"),
        ("API", "FastAPI, SQLAlchemy, pandas/NumPy (Monte Carlo engine), pyotp"),
    ]
    for j, (head, color, rows) in enumerate([("Google Cloud AI", VIOLET_DK, ai_rows),
                                             ("Data, platform and the app", INK, data_rows)]):
        cx = L + j * (cw + gap)
        box(slide, cx, ty, cw, th, fill=WHITE, line=LINE, r=0.12)
        text(slide, cx + 0.18, ty + 0.1, cw - 0.36, 0.28, P(head, size=11.5, font=SEMI, color=color), anchor="m")
        name_w = 1.62
        ry = ty + 0.44
        desc_w = cw - 0.36 - name_w
        heights = [max(estimate_height([P(d, size=10, line=0.95)], desc_w),
                       estimate_height([P(n, size=10, font=SEMI, line=0.95)], name_w - 0.08)) + 0.14
                   for n, d in rows]
        spare = (th - 0.52 - sum(heights)) / len(rows)
        for (name, desc), rh in zip(rows, heights):
            rh += max(0.0, spare)
            rule(slide, cx + 0.18, ry, cx + cw - 0.18, ry, color=HAIR)
            text(slide, cx + 0.18, ry + 0.03, name_w - 0.08, rh - 0.06, P(name, size=10, font=SEMI, line=0.95),
                 anchor="m")
            text(slide, cx + 0.18 + name_w, ry + 0.03, desc_w, rh - 0.06,
                 P(desc, size=10, color=INK, line=0.95), anchor="m")
            ry += rh


def s_cost(slide):
    y, h = TOP, BOT - TOP
    gap = 0.15
    w1, w2 = 1.95, 3.52
    w3 = W - w1 - w2 - 2 * gap
    x1, x2 = L, L + w1 + gap
    x3 = x2 + w2 + gap
    pad = 0.16

    # measured: the deployed prototype
    box(slide, x1, y, w1, h, fill=WHITE, line=LINE, r=0.12)
    pill(slide, x1 + pad, y + 0.18, 0.86, 0.24, "Measured", GREEN_TINT, GREEN, size=9)
    text(slide, x1 + pad, y + 0.5, w1 - 2 * pad, 0.26, P("Deployed prototype", size=12, font=SEMI))
    text(slide, x1 + pad, y + 0.86, w1 - 2 * pad, 0.56, P(T("about ", size=11, color=MUTED),
                                                         T("$9.40", size=28, font=SEMI, color=GREEN)), anchor="m")
    text(slide, x1 + pad, y + 1.42, w1 - 2 * pad, 0.7, [
        P("a month, baseline", size=11, after=3),
        P("Cloud SQL db-f1-micro;", size=9.5, color=MUTED),
        P("Cloud Run scales to zero", size=9.5, color=MUTED)])
    rule(slide, x1 + pad, y + 2.26, x1 + w1 - pad, y + 2.26, color=HAIR)
    text(slide, x1 + pad, y + 2.38, w1 - 2 * pad, 0.5, P(T("$3.39", size=24, font=SEMI, color=VIOLET_DK)),
         anchor="m")
    text(slide, x1 + pad, y + 2.9, w1 - 2 * pad, 1.05, [
        P("total AI spend on production so far, over 151 AI decisions", size=10.5, after=4),
        P("$2.29 of it was the live model checks", size=9.5, color=MUTED)])

    # measured: AI cost per action
    box(slide, x2, y, w2, h, fill=WHITE, line=LINE, r=0.12)
    pill(slide, x2 + pad, y + 0.18, 0.86, 0.24, "Measured", GREEN_TINT, GREEN, size=9)
    text(slide, x2 + pad, y + 0.5, w2 - 2 * pad, 0.26, P("AI cost per action", size=12, font=SEMI))
    text(slide, x2 + pad, y + 0.76, w2 - 2 * pad, 0.22, P("median, from the live AI decision log", size=9.5,
                                                         color=MUTED))
    rows = [
        ("Explanation: risk, X-ray, What-if", "$0.0018–0.0025"),
        ("Order explanation", "$0.0021"),
        ("Fund fit", "$0.0023"),
        ("Copilot question", "$0.0026"),
        ("Held-order review note (Pro)", "$0.011"),
        ("Call analysis", "$0.014"),
        ("AML case review (Pro)", "$0.018"),
        ("Proposal (Pro)", "$0.028"),
        ("Scenario grounding, Google Search", "$0.0435"),
        ("Document AI bank statement read", "$0.75"),
    ]
    vw = 1.07
    ry, rh = y + 1.06, 0.245
    for name, cost in rows:
        rule(slide, x2 + pad, ry, x2 + w2 - pad, ry, color=HAIR)
        text(slide, x2 + pad, ry, w2 - 2 * pad - vw, rh, P(name, size=9.5, line=0.95), anchor="m")
        text(slide, x2 + w2 - pad - vw, ry, vw, rh, P(cost, size=9.5, font=MED, align="r"), anchor="m")
        ry += rh
    rule(slide, x2 + pad, ry, x2 + w2 - pad, ry, color=HAIR)
    text(slide, x2 + pad, ry + 0.06, w2 - 2 * pad, 0.44, P(
        "Pro = Gemini 3.1 Pro; the other Gemini rows use 3.8 Flash. Document AI is the list price per statement; "
        "reading the CSV avoids it.", size=9, color=MUTED, line=0.95))

    # estimate: a firm with 10,000 clients
    box(slide, x3, y, w3, h, fill=WASH, line=LINE, r=0.12)
    pill(slide, x3 + pad, y + 0.18, 0.86, 0.24, "Estimate", WHITE, INK, size=9, line=MUTED)
    text(slide, x3 + pad, y + 0.5, w3 - 2 * pad, 0.26, P("A firm with 10,000 clients", size=12, font=SEMI))
    tw3 = w3 - 2 * pad
    text(slide, x3 + pad, y + 0.8, tw3, 0.46, P(
        "Assumed per client a month: 2 explanations, 1 Copilot question, 1 order explained; plus the firm-wide "
        "monthly volumes below.", size=9, color=MUTED, line=0.95))
    est = [
        ("20,000 explanations", "$0.0018–0.0025", "$36–50"),
        ("10,000 Copilot questions", "$0.0026", "$26.00"),
        ("10,000 orders explained", "$0.0021", "$21.00"),
        ("300 AML case reviews", "$0.018", "$5.40"),
        ("200 call analyses", "$0.014", "$2.80"),
        ("100 proposals", "$0.028", "$2.80"),
        ("30 statement reads", "$0.75", "$22.50"),
    ]
    cw_item, cw_unit = 1.55, 0.98
    cw_cost = tw3 - cw_item - cw_unit
    ry, rh = y + 1.3, 0.205
    for label, align, cx_, cw_ in [("Each month", "l", 0, cw_item), ("× unit cost", "r", cw_item, cw_unit),
                                   ("= cost", "r", cw_item + cw_unit, cw_cost)]:
        text(slide, x3 + pad + cx_, ry, cw_, rh, P(label, size=8.5, font=MED, color=MUTED, align=align),
             anchor="m", check=False)
    ry += rh
    for item, unit, cost in est:
        rule(slide, x3 + pad, ry, x3 + w3 - pad, ry, color=HAIR)
        text(slide, x3 + pad, ry, cw_item, rh, P(item, size=9, line=0.95), anchor="m")
        text(slide, x3 + pad + cw_item, ry, cw_unit, rh, P(unit, size=9, color=MUTED, align="r"), anchor="m")
        text(slide, x3 + pad + cw_item + cw_unit, ry, cw_cost, rh, P(cost, size=9, font=MED, align="r"),
             anchor="m")
        ry += rh
    rule(slide, x3 + pad, ry, x3 + w3 - pad, ry, color=MUTED)
    vw3 = 1.12
    sums = [("AI, a month", "$116.50–130.50", 0.23),
            ("Cloud Run + Cloud SQL, production tier", "about $300–600", 0.34),
            ("All in, a month", "about $417–731", 0.23)]
    ry += 0.05
    for k, (name, cost, rh_) in enumerate(sums):
        last = k == len(sums) - 1
        text(slide, x3 + pad, ry, tw3 - vw3, rh_, P(name, size=9.5, font=SEMI if last else MED, line=0.92),
             anchor="m")
        text(slide, x3 + w3 - pad - vw3, ry, vw3, rh_, P(cost, size=9.5, font=SEMI if last else MED, align="r",
                                                        color=GREEN if last else INK), anchor="m")
        ry += rh_
    text(slide, x3 + pad, ry + 0.02, tw3, 0.22, P("That is about 4–7 cents per client a month.", size=9.5,
                                                   font=MED, color=GREEN), anchor="m")


def s_snapshots(slide):
    cells = [
        ("daniel-ruth-call-flags.png", (195, 418, 1950),
         [T("Call intelligence. ", font=SEMI, color=INK), "Ruth Alvarez's call, 9 timestamped conduct flags"]),
        ("priya-nvda-guardian-top.png", (175, 165, 1965),
         [T("Pre-trade Guardian. ", font=SEMI, color=INK), "Priya's 60 NVDA order, held for advisor review"]),
        ("omar-rings-graph.png", (175, 196, 1965),
         [T("Fraud ring radar. ", font=SEMI, color=INK), "Four leads and a client share one device"]),
        ("omar-models-inventory.png", (175, 100, 1965),
         [T("Model Risk Office. ", font=SEMI, color=INK), "18 models with risk tier, owner and evidence"]),
    ]
    gx, gy = 0.2, 0.12
    cw = (W - gx) / 2
    rh = (BOT - TOP - gy) / 2
    ih = rh - 0.3
    for i, (fname, crop, cap) in enumerate(cells):
        cx = L + (i % 2) * (cw + gx)
        cy = TOP + (i // 2) * (rh + gy)
        shot(slide, fname, cx, cy, cw, ih, crop)
        text(slide, cx + 0.02, cy + ih + 0.04, cw, 0.25, P(*cap, size=10, color=MUTED), anchor="m")


def s_performance(slide):
    text(slide, L, 1.28, 5.6, 0.26, P(T("Measured on 18 Oct 2026 ", font=MED, color=INK),
                                      "on the live deployment, unless noted", size=10, color=MUTED), anchor="m")
    tiles = [
        ("699", "API tests passing (1 skipped) and 209 web unit tests, run before every deploy", INK),
        ("37/37", "live model-check suites passing on real Gemini (latest run, $0.35)", VIOLET_DK),
        ("29/29", "fresh live red-team attacks resisted; 12/12 fixed attack cases; AML scenarios caught 4/4 "
                  "mutations", VIOLET_DK),
        ("18/18", "fair-lending name pairs read the same (names hidden from Gemini)", VIOLET_DK),
        ("AUC 0.76", "Lead Score on 5,000 held-out leads vs a 0.75 gate (0.79 on BigQuery's split); 8/8 twin "
                     "pairs ordered correctly", VIOLET_DK),
        ("5/5", "case review golden set on Gemini Pro; the Flash challenger also 5/5, at $0.010", VIOLET_DK),
        ("100%", "reconciliation agent precision and recall, vs 62% recall for the scorer alone", VIOLET_DK),
        ("0.55 s", "What-if Monte Carlo: 10,000 paths over 15 years", INK),
        ("1.9 s", "median full page load; API median response 357 ms", INK),
    ]
    gx, gy = 0.1, 0.1
    gw = 5.98
    tw = (gw - 2 * gx) / 3
    top = 1.6
    th = (BOT - top - 2 * gy) / 3
    for i, (big, words, color) in enumerate(tiles):
        tx = L + (i % 3) * (tw + gx)
        ty = top + (i // 3) * (th + gy)
        box(slide, tx, ty, tw, th, fill=WHITE, line=LINE, r=0.1)
        text(slide, tx + 0.13, ty + 0.08, tw - 0.26, 0.36, P(big, size=18, font=SEMI, color=color), anchor="m")
        text(slide, tx + 0.13, ty + 0.46, tw - 0.22, th - 0.5, P(words, size=9, color=INK, line=0.96))

    # median AI latency, a native chart
    cx = L + gw + 0.16
    cwid = R - cx
    box(slide, cx, TOP, cwid, BOT - TOP, fill=WHITE, line=LINE, r=0.12)
    text(slide, cx + 0.16, TOP + 0.12, cwid - 0.32, 0.26, P("Median AI latency, seconds", size=11.5, font=SEMI),
         anchor="m")
    text(slide, cx + 0.16, TOP + 0.38, cwid - 0.32, 0.22, P(
        T("Darker: Gemini 3.1 Pro", color=VIOLET_DK, font=MED), "   lighter: Gemini 3.8 Flash", size=8.5,
        color=MUTED), anchor="m")
    cats = ["Explanations (3.2–4.1)", "Order explanation", "Fund fit", "Scenario shocks", "Copilot",
            "Review note (Pro)", "AML case review (Pro)", "Call analysis", "Reconciliation agent", "Proposal (Pro)"]
    vals = [3.6, 3.8, 3.6, 5.8, 8.7, 9.3, 15.0, 17.5, 17.5, 21.9]
    pro = {5, 6, 9}
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("Median latency", vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, In(cx + 0.04), In(TOP + 0.62), In(cwid - 0.12),
                                In(BOT - TOP - 0.7), cd)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = False
    ch.font.name = REG
    ch.font.size = Pt(9)
    ch.font.color.rgb = rgb(INK)
    plot = ch.plots[0]
    plot.gap_width = 45
    plot.vary_by_categories = False
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = rgb(VIOLET)
    for i in range(len(vals)):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(VIOLET_DK if i in pro else VIOLET)
        pt.format.line.fill.background()
    dl = ser.data_labels
    dl.show_value = True
    dl.show_category_name = False
    dl.show_series_name = False
    dl.show_legend_key = False
    dl.number_format = '0.0" s"'
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(9)
    dl.font.name = MED
    dl.font.color.rgb = rgb(INK)
    cat = ch.category_axis
    cat.reverse_order = True
    cat.major_tick_mark = XL_TICK_MARK.NONE
    cat.format.line.color.rgb = rgb(HAIR)
    cat.tick_labels.font.size = Pt(9)
    cat.tick_labels.font.color.rgb = rgb(INK)
    val = ch.value_axis
    val.minimum_scale = 0
    val.maximum_scale = 28
    val.has_major_gridlines = False
    val.major_tick_mark = XL_TICK_MARK.NONE
    val.tick_label_position = XL_TICK_LABEL_POSITION.NONE
    val.format.line.fill.background()
    val.visible = False


def s_future(slide):
    cols = [
        ("Now", "live today", GREEN_TINT, None, [
            (None, "Acquire, Invest, Trade and Operate live, with Govern across all four"),
            (None, "On Cloud Run and Firebase, with Gemini 3.1 Pro and 3.8 Flash"),
            (None, "18 models under the Model Risk Office"),
            (None, "Paper trading at live US market prices"),
        ]),
        ("Next", "", WHITE, LINE, [
            ("ai", "A Gemini Live voice advisor: clients talk to Atrium inside the same guardrails"),
            ("firebase", "Push alerts through Firebase Cloud Messaging: the live inbox on every phone"),
            ("fraud", "Fraud signals shared across firms in BigQuery data clean rooms, never the client data"),
            ("ai", "Agents that keep every KYC file current"),
        ]),
        ("Later", "", WASH, LINE, [
            (None, "Real brokerage execution (Alpaca live / FIX) and more markets"),
            (None, "Agent-to-agent (A2A) links to custodians and fund administrators"),
            (None, "Continuous model monitoring with Vertex AI"),
            (None, "Sanctions and PEP screening"),
            (None, "Client statements and tax reports"),
        ]),
    ]
    gap = 0.34
    cw = (W - 2 * gap) / 3
    top = TOP
    note_h = 0.46
    ch = BOT - note_h - 0.14 - top
    for i, (head, sub, fill, line, items) in enumerate(cols):
        cx = L + i * (cw + gap)
        box(slide, cx, top, cw, ch, fill=fill, line=line, r=0.12)
        text(slide, cx + 0.2, top + 0.14, cw - 0.4, 0.3, P(T(head, size=15, font=SEMI),
                                                          T("  " + sub, size=9.5, color=GREEN, font=MED) if sub
                                                          else T("")), anchor="m")
        iy = top + 0.6
        for kind, words in items:
            tx = cx + 0.56
            para = P(words, size=10.5, line=0.98)
            th = estimate_height([para], cx + cw - 0.18 - tx)
            if kind:
                icon_disc(slide, cx + 0.2, iy - 0.04, 0.26, kind)
            else:
                circle(slide, cx + 0.28, iy + 0.04, 0.1, fill=GREEN if i == 0 else MUTED)
            text(slide, tx, iy - 0.02, cx + cw - 0.18 - tx, th + 0.04, para)
            iy += th + 0.16
        if i < 2:
            ax = cx + cw + 0.06
            rule(slide, ax, top + 0.29, ax + gap - 0.12, top + 0.29, color=MUTED, lw=1.2, arrow=True)
    ny = BOT - note_h
    note = box(slide, L, ny, W, note_h, fill=WHITE, line=LINE, r=0.12)
    icon_disc(slide, L + 0.14, ny + 0.1, 0.26, "person")
    text(slide, L + 0.52, ny, W - 0.7, note_h, P(T("Responsible AI. ", font=SEMI), "People decide every "
                                                 "consequential action; every AI decision is logged with its model, "
                                                 "prompt version, cost and the person who acted.", size=10.5),
         anchor="m")


def _shorten(url, face, size, room_in):
    """The address as shown when even a whole line is too narrow: cut before the tail; the link stays whole."""
    if _pil_text_width(url, face, size) <= room_in:
        return url
    for n in range(len(url) - 9, 12, -1):
        shown = url[:n] + "…" + url[-8:]
        if _pil_text_width(shown, face, size) <= room_in:
            return shown
    return url[:20] + "…"


def _add_link(p, lead, url, avail_in, size=11.5):
    """A soft line break, a muted lead-in and the link. A link that does not fit beside its lead-in drops to a line
    of its own, then shrinks (to 9 pt), then is shown shortened; it always opens the full address."""
    is_url = url.startswith("http")
    p.add_line_break()
    if lead:
        r = p.add_run()
        r.text = lead
        style_run(r, size, REG, MUTED)
    room = avail_in - (_pil_text_width(lead, REG, size) if lead else 0.0)
    s = size
    lines = 1
    if _pil_text_width(url, MED, s) > room:
        if lead:
            p.add_line_break()
            room = avail_in
            lines = 2
        while _pil_text_width(url, MED, s) > room and s > 9:
            s -= 0.5
    shown = _shorten(url, MED, s, room) if is_url else url
    r = p.add_run()
    r.text = shown
    style_run(r, s, MED, GREEN if is_url else CORAL_DK, link=url if is_url else None)
    if not is_url:
        WARNINGS.append(f"slide 13: link placeholder {url!r} still to fill in LINKS")
    return lines


def s_links(slide):
    tb = text_shape(slide, "Provide links to your:")
    box_w = 5.3
    tb.width = In(box_w)
    tf = tb.text_frame
    ps = tf.paragraphs
    ps[1]._p.find(qn("a:endParaRPr")).set("sz", "700")
    avail = box_w - 0.2 - 0.5  # the box insets and the bullet indent
    link_lines = {
        2: [("", LINKS["github"])],
        3: [("Demo video (3:53): ", LINKS["video_short"]),
            ("Extended walkthrough (7:49): ", LINKS["video_long"])],
        4: [("", LINKS["product"]), ("also ", LINKS["product_alt"])],
    }
    used = 0.27 + 0.12 + 0.2  # the heading, the gap paragraph and the box insets, in inches
    for idx, lines in link_lines.items():
        p = ps[idx]
        used += 0.23 + 0.11  # the template's label and the space after it
        for r in p.runs:
            r.font.size = Pt(14)
        # the template's "●" is not in Google Sans Flex (PowerPoint would borrow another font): use its "•"
        pPr = p._p.find(qn("a:pPr"))
        pPr.find(qn("a:buChar")).set("char", "•")
        pPr.find(qn("a:buFont")).set("typeface", REG)
        bsz = pPr.find(qn("a:buSzPts"))
        if bsz is not None:
            bsz.set("val", "2000")
        for lead, url in lines:
            used += 0.19 * _add_link(p, lead, url, avail)
        spc = p._p.find(qn("a:pPr")).find(qn("a:spcAft"))
        spc.find(qn("a:spcPts")).set("val", "800")
        end = p._p.find(qn("a:endParaRPr"))
        p._p.remove(end)
        p._p.append(end)
    drop_paragraphs_after(tf, 5)
    tb.height = In(2.9)
    if used > 2.9:
        WARNINGS.append(f"slide 13: the links may run into the 'How to try it' box ({used:.2f} in > 2.90 in); "
                        "use shorter links")

    # the real "choose a person" screen
    shot(slide, "public-login.png", 5.78, TOP, R - 5.78, 2.14, (180, 12, 1820))

    # how to try it
    y0 = 3.66
    hh = BOT - y0
    box(slide, L, y0, W, hh, fill=WASH, line=LINE, r=0.12)
    text(slide, L + 0.22, y0 + 0.18, 3.0, 0.3, P("How to try it", size=13, font=SEMI), anchor="m")
    text(slide, L + 0.22, y0 + 0.52, 3.0, 1.1, [
        P("Open the link and choose a person. No password.", size=11, after=5),
        P("Every person, account and trade is synthetic; trading uses paper money at real US market prices.",
          size=9.5, color=MUTED)])
    people = [(["PR"], "Priya", "investor"), (["DO"], "Daniel", "advisor"),
              (["MT", "SO"], "Mei or Sam", "operations"), (["OH"], "Omar", "compliance")]
    px0 = L + 3.45
    pg = 0.12
    pw = (R - 0.2 - px0 - 3 * pg) / 4
    ph = 1.22
    py = y0 + (hh - ph) / 2
    for i, (ini, name, role) in enumerate(people):
        px = px0 + i * (pw + pg)
        box(slide, px, py, pw, ph, fill=WHITE, line=LINE, r=0.1)
        for k, s in enumerate(ini):
            person(slide, px + 0.16 + k * 0.32, py + 0.16, s, d=0.4, size=10)
        text(slide, px + 0.16, py + 0.66, pw - 0.3, 0.26, P(name, size=12, font=SEMI), anchor="m")
        text(slide, px + 0.16, py + 0.9, pw - 0.3, 0.22, P(role, size=10, color=MUTED), anchor="m")


def s_trust(slide, title_el):
    el = copy.deepcopy(title_el)
    tree = slide.shapes._spTree
    ids = [int(e.get("id")) for e in tree.iter(qn("p:cNvPr"))]
    el.find(qn("p:nvSpPr")).find(qn("p:cNvPr")).set("id", str(max(ids) + 1))
    tree.insert_element_before(el, "p:extLst")
    title = slide.shapes[-1]
    title.text_frame.paragraphs[0].runs[0].text = "How Atrium keeps the AI honest"

    x, y, w, h = diagram(slide, "atrium-ai-trust.png", L, TOP + 0.02, 6.72, 3.2, align="l")
    cap = P(T("Read left to right: ", font=MED, color=INK), "grounded inputs, Gemini, deterministic checks, a "
            "person decides, the decision log; the Model Risk Office watches the whole loop.", size=10,
            color=MUTED, line=0.98)
    cap_h = estimate_height([cap], w - 0.1)
    cy = y + h + 0.1
    text(slide, x + 0.05, cy, w - 0.1, cap_h + 0.04, cap)
    # the decision log itself, as recorded in production
    sy = cy + cap_h + 0.12
    shot(slide, "omar-decision-log-table.png", x, sy, w, BOT - sy, (180, 150, 1965), r=0.05)
    fx = x + w + 0.2
    fw = R - fx
    facts = [
        ("37/37", VIOLET_DK, "live model-check suites pass on real Gemini, run after each deploy"),
        ("29/29", CORAL_DK, "fresh red-team attacks resisted; a tripwire stops steered text from closing an "
                            "alert"),
        ("151", GREEN, "AI decisions on production so far, each logged with its model and cost: $3.39 in all"),
    ]
    fgap = 0.12
    fh = (BOT - y - 2 * fgap) / 3
    for i, (big, color, words) in enumerate(facts):
        fy = y + i * (fh + fgap)
        box(slide, fx, fy, fw, fh, fill=WHITE, line=LINE, r=0.1)
        text(slide, fx + 0.16, fy + 0.14, fw - 0.32, 0.4, P(big, size=22, font=SEMI, color=color), anchor="m")
        text(slide, fx + 0.16, fy + 0.6, fw - 0.28, fh - 0.68, P(words, size=10, line=0.98))


# =========================================================================================================
def office_export(src: Path, pptx: Path | None, pdf: Path | None, png_dir: Path | None) -> None:
    ps1 = r'''
param([string]$Src, [string]$Pptx, [string]$Pdf, [string]$PngDir)
$ErrorActionPreference = "Stop"
$app = New-Object -ComObject PowerPoint.Application
try {
  $pres = $app.Presentations.Open($Src, -1, 0, 0)
  try {
    if ($PngDir) {
      New-Item -ItemType Directory -Force -Path $PngDir | Out-Null
      foreach ($s in $pres.Slides) {
        $s.Export((Join-Path $PngDir ("slide-{0:D2}.png" -f $s.SlideIndex)), "PNG", 1920, 1080)
      }
    }
    if ($Pdf) { $pres.SaveAs($Pdf, 32) }
    if ($Pptx) { $pres.SaveAs($Pptx, 24, -1) }
  } finally { $pres.Close() }
} finally {
  # close PowerPoint, unless it is holding presentations of yours that were already open
  if ($app.Presentations.Count -eq 0) { $app.Quit() }
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "export.ps1"
        script.write_text(ps1, encoding="utf-8")
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
               "-Src", str(src), "-Pptx", str(pptx or ""), "-Pdf", str(pdf or ""), "-PngDir", str(png_dir or "")]
        subprocess.run(cmd, check=True)


def set_theme_link_colour(prs, colour: str) -> None:
    """Hyperlinks take the theme's link colour in PowerPoint; make it Atrium green instead of the template teal."""
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT

    theme = prs.slide_master.part.part_related_by(RT.THEME)
    xml = theme.blob.decode("utf-8")
    for tag in ("hlink", "folHlink"):
        xml = re.sub(r'(<a:%s>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}' % tag, r"\g<1>" + colour, xml)
    theme._blob = xml.encode("utf-8")


def build(template: Path, raw_out: Path) -> None:
    prs = Presentation(str(template))
    delete_slide(prs, 1)  # the "please download this template" note
    set_theme_link_colour(prs, GREEN)
    slides = list(prs.slides)
    if len(slides) != 15:
        raise SystemExit(f"expected 15 slides after removing the note, found {len(slides)}")
    title_el = text_shape(slides[1], "Brief about the idea")._element
    builders = [s_title, s_brief, s_opportunities, s_features, s_flow, s_mocks, s_architecture, s_tech, s_cost,
                s_snapshots, s_performance, s_future, s_links]
    for i, fn in enumerate(builders):
        CURRENT[0] = i + 1
        fn(slides[i])
    CURRENT[0] = 14
    s_trust(slides[13], title_el)
    # slide 15 (the thank-you art) stays as it is
    prs.save(str(raw_out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", type=Path, default=None)
    ap.add_argument("--png", type=Path, default=None, help="also export each slide as PNG into this folder")
    ap.add_argument("--no-office", action="store_true", help="skip PowerPoint (no PDF, fonts not embedded)")
    args = ap.parse_args()
    template = args.template or (TEMPLATE_COPY if TEMPLATE_COPY.exists() else TEMPLATE_DOWNLOAD)
    if not template.exists():
        raise SystemExit(f"template not found: {template}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "atrium-raw.pptx"
        build(template, raw)
        if args.no_office:
            shutil.copyfile(raw, OUT_PPTX)
            print(f"wrote {OUT_PPTX} (python-pptx only)")
        else:
            office_export(raw, OUT_PPTX, OUT_PDF, args.png.resolve() if args.png else None)
            print(f"wrote {OUT_PPTX}\nwrote {OUT_PDF}")
            if args.png:
                print(f"wrote slide PNGs to {args.png}")
    for w in WARNINGS:
        print("warning:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())

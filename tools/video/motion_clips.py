"""Motion clips for the films: timed to the narration's words, rendered frame by frame with motion blur.

A clip is an HTML fragment in tools/video/motion/clips, written for the motion engine in tools/video/motion/engine
(MIT, from the motion-broll kit: one shape that morphs between states, every style a pure function of time). The
fragment reads its timing from `__DATA__`: when each sentence starts, when each word is said, and the captions.
Here it is filled in, built into one self-contained page with Atrium's fonts, and rendered with motion blur.

Setup once: `bash ~/.claude/skills/motion-broll/scripts/setup.sh tools/video/motion` (or `npm i playwright` in
tools/video/motion and `npx playwright install chromium`).
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE / "motion"
ENGINE = KIT / "engine"
FPS = 30

CHAPTERS = {
    1: ("Acquire", "Every lead scored for fit and for fraud before an advisor calls.", [("Daniel Okafor", "Advisor")]),
    2: ("Invest", "Portfolios tested against 10,000 futures drawn from real markets.",
        [("Priya Raman", "Investor"), ("Lucas Moreau", "Investor")]),
    3: ("Trade", "Every order checked before it reaches the market, and held when it looks wrong.",
        [("Priya Raman", "Investor"), ("Tom Becker", "Investor"), ("Daniel Okafor", "Advisor")]),
    4: ("Operate", "Statements reconciled, and two people for every change to the books.",
        [("Mei Tanaka", "Operations"), ("Sam Ortiz", "Operations")]),
    5: ("Protect and govern", "Financial crime caught with its evidence, and every model validated and watched.",
        [("Omar Haddad", "Compliance")]),
}
CHAPTER_SECONDS = 2.0


def _font(name: str) -> str:
    return base64.b64encode((KIT / "fonts" / name).read_bytes()).decode()


def brand_css() -> str:
    """Atrium's three voices, embedded so the rendered page needs nothing from the network."""
    return (f"@font-face{{font-family:'Schibsted Grotesk';src:url(data:font/woff2;base64,{_font('SchibstedGrotesk-normal.woff2')}) format('woff2');font-weight:400 900}}"
            f"@font-face{{font-family:'Newsreader';src:url(data:font/woff2;base64,{_font('Newsreader-normal.woff2')}) format('woff2');font-weight:400 600}}"
            f"@font-face{{font-family:'Newsreader';font-style:italic;src:url(data:font/woff2;base64,{_font('Newsreader-italic.woff2')}) format('woff2');font-weight:400 600}}")


def build(name: str, template: str, data: dict) -> tuple[Path, str]:
    """The clip filled with its data, as one self-contained page in motion/dist, and a digest of its source."""
    frag = (KIT / "clips" / f"{template}.html").read_text(encoding="utf-8")
    shared = (KIT / "clips" / "_atrium.js").read_text(encoding="utf-8")
    frag = frag.replace("/*ATRIUM*/", shared).replace("__DATA__", json.dumps(data)).replace("/*BRAND*/", brand_css())
    engine = "".join((ENGINE / f).read_text(encoding="utf-8") for f in ("motion.js", "base.css", "render.js"))
    (KIT / "work").mkdir(exist_ok=True)
    work = KIT / "work" / f"{name}.html"
    work.write_text(frag, encoding="utf-8")
    subprocess.run([sys.executable, str(ENGINE / "build.py"), str(KIT / "dist"), str(work)], check=True,
                   capture_output=True, env={**os.environ, "PYTHONUTF8": "1"})
    return KIT / "dist" / f"{name}.html", hashlib.sha256((frag + engine).encode()).hexdigest()[:16]


def render(name: str, template: str, data: dict, out: Path) -> Path:
    """Fill a clip with its data, build it and render it to `out` (.mp4, or .mov with alpha for an overlay).
    A render is kept while its source is unchanged."""
    page, digest = build(name, template, data)
    stamp = out.with_name(out.name + ".src")
    if out.exists() and stamp.exists() and stamp.read_text() == digest:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(["node", str(ENGINE / "render.js"), str(page), str(out), str(FPS)],
                          capture_output=True, text=True, env={**os.environ, "NODE_PATH": str(KIT / "node_modules")})
    if done.returncode != 0 or "ERR" in done.stdout:
        raise RuntimeError(f"render of {name} failed: {done.stdout[-400:]} {done.stderr[-400:]}")
    stamp.write_text(digest)
    return out


def stills(page: Path, times: list[float], out: Path) -> Path:
    """A contact sheet of a built clip at these times, to look at before rendering."""
    done = subprocess.run(["node", str(ENGINE / "beats.js"), str(page), str(out), *[f"{t:.2f}" for t in times]],
                          capture_output=True, text=True, env={**os.environ, "NODE_PATH": str(KIT / "node_modules")})
    if done.returncode != 0 or "ERR" in done.stdout:
        raise RuntimeError(f"stills of {page.name} failed: {done.stdout[-600:]} {done.stderr[-600:]}")
    return out

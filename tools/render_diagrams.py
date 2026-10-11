"""Render every ```mermaid block in the blueprint to docs/diagrams/*.svg via mermaid-cli.

The Markdown keeps its mermaid fences (GitHub renders them natively); the PDF build
inlines these SVGs instead of rendering mermaid in the page, which is unreliable
under headless printing.

Usage:  python tools/render_diagrams.py            (re-renders only changed blocks)
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "docs" / "Atrium-Product-Blueprint.md"
OUT_DIR = ROOT / "docs" / "diagrams"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MMDC = ["npx", "-y", "@mermaid-js/mermaid-cli@11", ]

MERMAID_CONFIG = {
    "theme": "neutral",
    "themeVariables": {"fontFamily": "Segoe UI, Arial, sans-serif", "fontSize": "16px"},
    "flowchart": {"htmlLabels": True, "useMaxWidth": False, "padding": 14, "nodeSpacing": 30,
                  "rankSpacing": 45},
    "sequence": {"useMaxWidth": False, "width": 150, "messageFontSize": 15, "actorFontSize": 16,
                 "actorMargin": 40},
}


def mermaid_blocks(md_text: str) -> list[str]:
    return re.findall(r"```mermaid\n(.*?)```", md_text, flags=re.S)


def block_id(src: str) -> str:
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:10]


def render(src: str, idx: int, out_svg: Path, work: Path) -> None:
    mmd = work / f"d{idx}.mmd"
    mmd.write_text(src, encoding="utf-8")
    pcfg = work / "puppeteer.json"
    pcfg.write_text(json.dumps({"executablePath": CHROME, "args": ["--no-sandbox"]}), encoding="utf-8")
    mcfg = work / "mermaid.json"
    mcfg.write_text(json.dumps(MERMAID_CONFIG), encoding="utf-8")
    cmd = MMDC + ["-p", str(pcfg), "-c", str(mcfg), "-i", str(mmd), "-o", str(out_svg),
                  "-b", "white", "-I", f"atrium-diagram-{idx}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, shell=True)
    if r.returncode != 0 or not out_svg.exists():
        raise RuntimeError(f"mmdc failed for diagram {idx}:\n{r.stdout}\n{r.stderr}")


def main() -> None:
    md_text = MD_PATH.read_text(encoding="utf-8")
    blocks = mermaid_blocks(md_text)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    work = Path(tempfile.mkdtemp(prefix="atrium-mmd-"))
    new_manifest = {}
    for idx, src in enumerate(blocks, start=1):
        bid = block_id(src)
        out_svg = OUT_DIR / f"diagram-{idx:02d}.svg"
        if manifest.get(str(idx)) == bid and out_svg.exists():
            print(f"diagram {idx}: unchanged")
        else:
            print(f"diagram {idx}: rendering ...", flush=True)
            render(src, idx, out_svg, work)
            print(f"diagram {idx}: ok ({out_svg.stat().st_size} bytes)")
        new_manifest[str(idx)] = bid
    manifest_path.write_text(json.dumps(new_manifest, indent=2), encoding="utf-8")
    print(f"rendered {len(blocks)} diagrams into {OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())

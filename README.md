# Atrium — AI Builder Cup 2026 (BFSI track)

Team **Ctrl+Alt+Hiru**. Theme: *BFSI: Intelligent Risk, Fraud & Financial Experiences*.

Atrium is an AI-native wealth operating system for US and global markets:
**Acquire → Invest → Trade → Operate**, with Gemini, ADK agents, BigQuery and Document AI
doing the scoring, explaining, guarding and reconciling at every step.

## Documents

| File | What it is |
|---|---|
| `docs/Atrium-Product-Blueprint.md` | The design blueprint (what we build, features, AI design, architecture, 7-day plan, submission checklist) |
| `docs/Atrium-Product-Blueprint.pdf` | The same, as a printable PDF with bookmarks |
| `docs/diagrams/*.svg` | Pre-rendered diagrams used by the PDF and reusable in the deck |

## Rebuilding the PDF

Requires Python 3.12 with `markdown` and `pymupdf`, Node 18+ (for `npx`), and Google Chrome.

```bash
python tools/render_diagrams.py   # mermaid fences -> docs/diagrams/*.svg (only changed ones)
python tools/build_pdf.py         # markdown -> HTML -> PDF, then footer, bookmarks, TOC pages
```

## Key dates (2026)

- 18 Oct — prototype submission deadline (deployed link, video < 3 min, public repo, PDF deck)
- 19 Oct – 6 Nov — evaluation; 7 Nov — finalists; 4 Dec — Grand Finale, Singapore
